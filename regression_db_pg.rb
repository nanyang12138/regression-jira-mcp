require 'rubygems'
require 'pg'
require 'singleton'
require 'timeout'
require 'facets/string'
require 'benchmark'

# Hooks into Event Machine for callbacks on events we are interested in logging into a db
# Very lightweight callbacks simply get a mutex, and add to @events queue, so it should
# not hold up Event Machine.
# Another @logger_thread is run to work off the contents of @events and translate the
# event into one or more db commands.
#
# Important: is uses async_exec which will not return until the command is complete like
# exec(), but does not block other ruby threads from running, unlike exec

# Presumes the existence of $logger created by main dj script
unless Dj.defines["REGRESSION_DISABLE_PREAMBLE"]
    preamble do
        regression_db_start
    end
end

unless Dj.defines["REGRESSION_DISABLE_POSTAMBLE"]
    postamble do
        regression_db_stop
    end
end

def regression_db_start
    # Set up connection to postgres database
    begin
        AmdPgDb.instance.start
    rescue => e
        $logger.info "Preamble rescued #{e.to_s}, #{e.class}"
        $logger.info e.backtrace
    end
end

def regression_db_stop(failure=false)
    begin
        AmdPgDb.instance.flush_and_exit(failure)
    rescue =>e
        $logger.info "Postamble Rescued #{e.to_s}, #{e.class}"
        $logger.info e.backtrace
    end
end


class EventStats
    def initialize
        @stats = Hash.new { |hash,k| hash[k]=[0,0] }
    end

    # Update statistics
    # duration should be in sec
    def update(type,duration)
        @stats[type][0] += 1
        @stats[type][1] += duration
    end

    def compute_total
        t = [0,0]
        @stats.each_pair do |k,v|
            t[0] += v[0]
            t[1] += v[1]
        end
        @stats["Total"] = t
    end

    # Return the stats report as a string
    def to_s
        compute_total
        fmt = "%-25s %10s %13s\n"
        s = fmt % ["EventType","Count","Duration(sec)"]
        @stats.each_pair do |k,v|
            s << fmt % [ k, v[0], "%10.2f" % v[1] ]
        end
        s
    end
end
$RRID=nil
class AmdPgDb
    include Singleton

    def started?
        @started
    end

    def initialize
        @events          = []
        @stats           = EventStats.new
        @db              = nil
        @db_con_proc     = nil
        @mutex           = Mutex.new
        @started         = false
        @subscriptions   = {}

        # Locally cached copies of tabls
        @tsmap    = {}
        @archmap  = {}
        @confmap  = {}
        @groupmap = {}
        @blockmap = {}

        if Dj.is_lite_mode? && ENV['RRID']
            @rrid = ENV['RRID']
        else
            @rrid = nil
        end
        @pname    = nil
        @pid      = nil
        @rname    = nil
        @cid      = nil
        @lastpass = nil
        @table    = nil
        @test_counts = {}

        @db_id_pg_jcid = 1

        init_subscriptions
        init_db
    end

    def init_subscriptions
        @subscriptions[:test_start] = event_subscribe(:test_start) do |d, t|
            @mutex.synchronize { @events << {:event=>:test_start, :test=>t} }
        end

        @subscriptions[:dj_tdl_suite_instantiated] = event_subscribe(:dj_tdl_suite_instantiated) do |s|
            @mutex.synchronize { @events << {:event=>:dj_tdl_suite_instantiated, :suite=>s} }
        end

        @subscriptions[:dj_cmd_done] = event_subscribe(:dj_cmd_done) do |cmd_spec, v|
            unless v.current_cmd_node && v.current_cmd_node.respond_to?(:ignored_for_regression) && v.current_cmd_node.ignored_for_regression
            @mutex.synchronize { @events << {:event=>:dj_cmd_done, :action_node=>v.current_node, :node=>v.current_cmd_node, :cmd_spec=>cmd_spec, :time=>Time.now.ctime} }
            end
        end

        @subscriptions[:dj_cmd_assigned] = event_subscribe(:dj_cmd_assigned) do |cmd_spec, v|
            unless v.current_cmd_node && v.current_cmd_node.respond_to?(:ignored_for_regression) && v.current_cmd_node.ignored_for_regression
            @mutex.synchronize { @events << {:event=>:dj_cmd_assigned, :node=>v.current_cmd_node, :cmd_spec=>cmd_spec, :time=>Time.now.ctime} }
            end
        end

        @subscriptions[:dj_new_node] = event_subscribe(:dj_new_node) do |node|
            @mutex.synchronize { @events << {:event=>:dj_new_node, :node=>node} }
        end

        @subscriptions[:dj_action_exit] = event_subscribe(:dj_action_exit) do |visitor|
            node = visitor.current_node
            @mutex.synchronize { @events << {:event=>:dj_action_exit, :node=>node, :timestamp=>Time.now.ctime } }
        end

        if !Dj.is_lite_mode?
            @subscriptions[:dj_done] = event_subscribe(:dj_done) do
                @mutex.synchronize { @events << {:event=>:dj_done} }
            end
        end
    end

    action :update_test_totals do
        begin
            ENV['DJ_SUITE_SEL'].split(/\s+/).each do |sn|
                sn = "#{ENV['DJ_TOP_COMPONENT']}::#{sn}" if sn !~ /::/
                s = send_suite(sn)
                ts = get_testcases(:all, :from=>s, :where=>"#{ENV['DJ_CNT_TEST_SEL']}")
                while @events.size > 0
                    Thread.pass
                end
                if !s.respond_to?(:db_id_pg)
                    suite_found(s)
                end
                bid = s.db_id_pg
                update_total_test_count(bid, ts.size)
            end
        rescue => ee
            $logger.error "#{ee}"
        end
    end

    def remove_subscriptions
        @subscriptions.each_pair do |k,v|
            event_unsubscribe(k, v)
        end
        @subscriptions.clear
    end

    def init_db
        @logger_thread = Thread.new do
            Thread.stop
            idle_counter = 0
            while true
                if @events.size > 0
                    finished = false
                    # firewall may cut down idle connection after 1 hour, etc.
                    # after idle 10 mins, re-conect
                    if idle_counter > 60*10
                        begin
                            @db.flush
                            @db.finish
                        rescue Exception => e
                        ensure
                            finished = true
                        end
                    end
                    idle_counter = 0
                    if (finished || @db.status() != PG::Connection::CONNECTION_OK)
                         $logger.warn "re-connect db!"
                         @db_con_proc.call
                         $logger.warn "re-connect db failed!" unless @db
                    end
                    # We peek and shift at the end because we don't want
                    # the event count to go to zero until we've actually
                    # finished processing all events. Otherwise, this
                    # thread may be terminated prematurely.
                    begin
                        while e = peek_event
                        # 5 mins time out so that we will not hang if connection is bad.
                          # Timeout::timeout(60*5) {
                              t = Benchmark.measure {
                                  case e[:event]
                                  when :test_start
                                      t = e[:test]
                                      # If we are an Actor, then insert the id into the actors table
                                      test_status(t, 'submitted')
                                      test_seed(t)
                                  when :dj_tdl_suite_instantiated
                                      suite = e[:suite]
                                      suite_found(suite)
                                  when :dj_cmd_done
                                      node     = e[:node]
                                      cmd_spec = e[:cmd_spec]
                                      #node.db_time_pg_end = e[:time]
                                      cmd_done(node, cmd_spec, e[:time])
                                      job_complete(node, node.db_time_pg_start, e[:timestamp])

                                      action_node = e[:action_node]
                                      action_name = action_node.comp_action
                                      ntt         = action_node.receiver
                                      if ntt.is_a?(TDL::TestCase) && (action_name =~ /run_dv.*$/ || action_name =~ /simctrl$/ || action_name =~ /dispatch_cmd_batch$/)
                                        req_MB = Integer(cmd_spec[:agenttype][:lsf_opts][:mem]) rescue 0
                                        peak_kB = Integer(cmd_spec[:peak_mem]) rescue 0
                                        update_mem_usage(ntt, peak_kB, req_MB);
                                      #else
                                      #  $logger.info "regression_db_pg: not updating mem usage, TDL tc=#{ntt.is_a?(TDL::TestCase)} action_name=#{action_name}"
                                      end

                                  when :dj_cmd_assigned
                                      node = e[:node]
                                      ntt  = node.receiver
                                      action_name = node.comp_action_args
                                      #if action_name =~ /(.*)\.run_dv:.*$/
                                      #    require 'ruby-debug'
                                      #    debugger
                                      #end
                                      if ntt.kind_of?(TDL::TestCase) #&& action_name == 'runner'
                                          test_status(ntt, "running")
                                      end
                                      node.db_time_pg_start = e[:time]
                                      cmd_started(node, e[:cmd_spec], e[:time])
                                when :dj_new_node
                                    node = e[:node]
                                    if node.type == :action
                                    elsif node.type == :cmd
                                        new_job(node)
                                        new_cmd(node)
                                    end
                                  when :dj_action_exit
                                      node = e[:node]
                                      ntt  = node.receiver
                                      action_name = node.comp_action
                                      if (ntt.kind_of?(TDL::TestCase) && (action_name =~ /runner/ || Dj.is_lite_mode?))
                                          status = node.exception ? 'failed' : 'passed'
                                          failed_ref = nil
                                          bfs = Dj::ActionGraph.instance.bfs_search_tree_from(node)
                                          tsi = bfs.topsort_iterator
                                          job_run_ids = []
                                          tsi.each do |v|
                                              if v.type == :cmd && v.db_id_pg_jrid
                                                  # TODO The last action that fails isn't necessarily
                                                  # the one that actually causes the test to fail. To know
                                                  # which action really caused the failure, you have to find
                                                  # the one(s) with failing paths back to the root node
                                                  if v.exception && v.exception.to_i != 0
                                                      failed_ref = v.db_id_pg_jrid
                                                  end
                                                  job_run_ids << v.db_id_pg_jrid
                                              end
                                          end
                                          map_jobs_to_test(job_run_ids, ntt)
                                          if status == "passed"
                                              failed_ref = nil
                                          elsif failed_ref == nil
                                            failed_ref = node.db_id_pg_jrid
                                          end
                                          test_complete(ntt, status, nil, nil, nil, nil, nil, failed_ref, nil) if !Dj.application.defines['RUN_SIM_ON_CLOUD']
                                      end
                                  when :dj_done
                                    if !Dj.is_lite_mode?
                                      remove_subscriptions
                                    end
                                  end
                              }
                              threshold_time = 10.0e0
                              @stats.update(e[:event],t.total)
                              $logger.warn "#{e[:event]} took #{t.total} sec, events queue=#{@events.size}" if t.total > threshold_time
                         #}
                              shift_event
                        end
                    rescue Exception => e
                        shift_event
                        $logger.warn "regression_db_pg.rb: #{e}"
                        $logger.warn e.backtrace.join("\n")
                    end
                else
                    idle_counter += 1
                    sleep 1
                end
            end
        end

        db         = ENV['PGDATABASE'] # "gcb_milos"
        host       = ENV['PGHOST'] # "lfweb2.atitech.com"
        port       = ENV['PGPORT'] || 5432
        user       = ENV['PGUSER'] # "orlvalid"
        passwd     = ENV['PGPASSWORD'] # "hamhocks"

        @db_con_proc = ->{
            @db = PG::Connection.open(dbname: db, host: host, port: port, user: user, password: passwd)
        }
        begin
            @db_con_proc.call
        rescue => e
            $logger.info "error in connecting DB#{e}"
        end
        if !@db
            $logger.fatal "Unable to connect to PGSQL database! Please check your environment variables"
            return
        end

        query = "SELECT version()"
        ver, = select_first(query)
        ver =~ /PostgreSQL ([^ ]+)/
        @pg_ver = $1
        @pg_ver_major, @pg_ver_minor, @pg_ver_subminor = @pg_ver.split('.').collect do |i|; i.to_i; end

        # cache some frequently used tables
        query = 'SELECT test_status_name, test_status_id FROM test_status'
        select_all(query) do |tsn, ts|
            @tsmap[tsn] = Integer(ts)
        end

        query = 'SELECT arch_name, arch_id FROM arch'
        select_all(query) do |arch_name, arch_id|
            @archmap[arch_name] = Integer(arch_id)
        end

        query = 'SELECT conf_name, conf_id FROM conf'
        select_all(query) do |conf_name, conf_id|
            @confmap[conf_name] = Integer(conf_id)
        end

        query = 'SELECT test_group_name, test_group_id FROM test_group'
        select_all(query) do |test_group_name, test_group_id|
            @groupmap[test_group_name] = Integer(test_group_id)
        end

        query = 'SELECT block_name, block_id FROM block'
        select_all(query) do |block_name, block_id|
            @blockmap[block_name] = Integer(block_id)
        end

        create_tables if !ENV['RRID']

        query = <<END
SELECT p.project_name, p.project_id
    FROM project p JOIN regression_run rr ON rr.project_ref = p.project_id
    WHERE rr.regression_run_id = $1
END
        @pname, @pid = select_first(query, @rrid)
        @pid = Integer(@pid)

        query = <<END
SELECT r.regression_name, r.category_ref
    FROM regression r JOIN regression_run rr ON rr.regression_ref = r.regression_id
    WHERE rr.regression_run_id = $1
END
        @rname, @cid = select_first(query, @rrid)
        @cid ||= 0
        @cid = Integer(@cid)

        @lastpass, = select_first("SELECT tablename FROM pg_tables WHERE tablename = 'last_pass'")
        # Postgres has a 63-character limit to table names.
        table   = "#{@pname}_#{@rname}_test_object_run"
        table63 = table[0,63]
        if table != table63
            $logger.warn "Database table name #{table} exceeds 63 characters and will be trunacted to #{table63}"
        end
        @table = "\"#{table63}\""

        # Add mem_usage column to tor table
        query = <<END
SELECT true as exists
FROM information_schema.columns
WHERE table_schema='public' and table_name='#{@table.unquote}' and column_name='mem_usage'
END
        has_mem_usage, = select_first(query)
        unless has_mem_usage
            query = <<END
ALTER TABLE #{@table} ADD mem_usage int;
END
            execute(query)
        end

        # Add lsf_req_MB column to the table
        query = <<END
SELECT true as exists
FROM information_schema.columns
WHERE table_schema='public' and table_name='#{@table.unquote}' and column_name='lsf_req_MB'
END
        has_lsf_req_MB, = select_first(query)
        unless has_lsf_req_MB
            query = <<END
ALTER TABLE #{@table} ADD "lsf_req_MB" int;
END
            execute(query)
        end
    end

    def select_first(q, *args)
        raise "No db connection" if !@db
        ret = []
        q = q + " LIMIT 1"
        @db.async_exec(q, args) do |res|
            ret = res.values.first
        end
        if block_given?
            yield ret
        end
        ret
    end

    def select_all(q, *args)
        raise "No db connection" if !@db
        ret = []
        @db.async_exec(q, args) do |res|
            ret = res.values
        end
        if block_given?
            ret.each do |row|
                yield row
            end
        end
        ret
    end

    def execute(q, *args)
        raise "No db connection" if !@db
        @db.async_exec(q, args) do |res|
        end
    end

    def create_tables
        proj       = ENV['DJ_CONTEXT'] || ENV['PROJECT']
        proj = proj.downcase
        tree       = ENV['TREE']
        tree = tree.downcase
        changelist = ENV['CHANGE']
        p4client   = ENV['P4CLIENT']
        log_dir    = ENV['LOGDIRECTORY']
        user       = ENV['USER']

        query = 'SELECT project_id FROM project WHERE project_name = $1'
        insert = <<END
INSERT INTO project (project_id, project_name, valid, status)
    VALUES (nextval('project_id_seq'), $1, TRUE, 'TRUE')
END

        @project_id = update_names(query, insert, proj)

        query = 'SELECT regression_id FROM regression WHERE regression_name = $1'
        insert = <<END
INSERT INTO regression (regression_id, regression_name, category_ref, valid)
    VALUES (nextval('regression_id_seq'), $1, 0, TRUE)
END
        rid = update_names(query, insert, tree)

        t = "#{proj}_#{tree}_test_object_run"
        query = "SELECT tablename FROM pg_tables WHERE tablename = '#{t}'"
        exist, = select_first(query)
        unless exist
            execute("CREATE TABLE #{t} AS SELECT * FROM test_object_run_template LIMIT 0")
            execute("ALTER TABLE #{t} SET WITHOUT OIDS")
            execute("CREATE INDEX #{t}_test_object_run_id_index ON \"#{t}\" (test_object_run_id)")
            execute("CREATE INDEX #{t}_regression_run_ref_index ON \"#{t}\" (regression_run_ref)")
            execute("CREATE INDEX #{t}_test_object_ref_index ON \"#{t}\" (test_object_ref)")
            execute("CREATE INDEX #{t}_test_status_ref_index ON \"#{t}\" (test_status_ref)")
        end

        @rrid, = select_first("SELECT nextval('regression_run_id_seq')")
	@rrid = Integer(@rrid)
        $RRID=@rrid
        status, = select_first("SELECT regression_status_id FROM regression_status WHERE regression_status_name = 'started'")
        iteration, = select_first('SELECT MAX(iteration) FROM regression_run WHERE changelist = $1 AND regression_ref = $2', changelist, rid)
        iteration ||= 0
	iteration = Integer(iteration)
        iteration += 1

        now = Time.now.ctime
        query = <<END
INSERT INTO regression_run
    (regression_run_id, project_ref, regression_ref, changelist, iteration,
    client, library_type, username, start_time, regression_status, log_directory)
    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
END
        execute(query, @rrid, @project_id, rid, changelist, iteration, p4client, nil, user, now, status, log_dir)

        t = "job_run_#{@rrid}"
        execute("CREATE TABLE job.#{t} (LIKE job.job_run_template INCLUDING ALL)")
        execute("ALTER TABLE job.#{t} SET WITHOUT OIDS")
        execute("CREATE SEQUENCE job.#{t}_job_run_id_seq");
        execute("ALTER TABLE job.#{t} ALTER COLUMN job_run_id SET DEFAULT nextval('job.#{t}_job_run_id_seq')")
        execute("ALTER SEQUENCE job.#{t}_job_run_id_seq OWNED by job.#{t}.job_run_id")
        execute("CREATE INDEX #{t}_job_run_id ON job.#{t} (job_run_id)")
        execute("CREATE INDEX #{t}_end_time ON job.#{t} (end_time)")

        t = "test_job_map_#{@rrid}"
        execute("CREATE TABLE job.#{t} AS SELECT * FROM job.test_job_map_template LIMIT 0")
        execute("ALTER TABLE job.#{t} SET WITHOUT OIDS")
        execute("CREATE INDEX #{t}_test_object_run_ref_index ON job.#{t} (test_object_run_ref)")
        execute("CREATE INDEX #{t}_job_run_ref_index ON job.#{t} (job_run_ref)")

        query = <<END
CREATE OR REPLACE VIEW job.test_job_product_#{@rrid} AS (
    SELECT * FROM job.job_run_#{@rrid}, job.test_job_map_#{@rrid}
        WHERE job_run_id = job_run_ref
)
END
        execute(query)

        query = <<END
CREATE OR REPLACE VIEW job.test_cpu_times_#{@rrid} AS (
    SELECT SUM(cpu_time) AS cpu_time, test_object_run_ref
        FROM job.test_job_product_#{@rrid}
        GROUP BY test_object_run_ref
)
END
        execute(query)

        t = "job_cmd_#{@rrid}"
        execute("CREATE TABLE job.#{t} (job_cmd_id  INTEGER NOT NULL,
                                        job_run_ref INTEGER,
                                        host        TEXT,
                                        gcf_id      INTEGER,
                                        cmd         TEXT,
                                        log_file    TEXT,
                                        start_time  TIMESTAMP WITHOUT TIME ZONE,
                                        end_time    TIMESTAMP WITHOUT TIME ZONE,
                                        exit_code   INTEGER)")
        execute("ALTER TABLE job.#{t} SET WITHOUT OIDS")
        execute("CREATE INDEX #{t}_job_run_ref_index ON job.#{t} (job_run_ref)")
        execute("CREATE SEQUENCE #{t}_id_seq INCREMENT 1 MINVALUE #{@db_id_pg_jcid}")
    end

    # suite instantiated
    def suite_found(block)
        if !block.respond_to?(:db_id_pg)
            if Dj.defines["REGRESSION_USE_SUITE_DAV_NAME"] || ENV["REGRESSION_USE_SUITE_DAV_NAME"]
                block.db_id_pg = update_block(block.dav_name)
            else
                block.db_id_pg = update_block(block.basename)
            end
        end
    end

    # entity instantiated
    def test_found(t)
        conf  = t.attrs[:configs].value.map{|c| c.to_s}.join('/')
        arch  = t.attrs[:configs].value.map{|c| c.respond_to?(:arch_name) ? c.arch_name : 'unknown_arch' }.join('/')
        group = t.has_attr?(:group) ? t.attrs[:group].value : 'common'

        suite_found(t.my_host_suite)
        t.db_id_pg_aid = update_arch(arch)
        t.db_id_pg_cid = update_conf(conf)
        t.db_id_pg_gid = update_group(group)

        begin
            if t.is_a?(TDL::TestCase::TestCaseFork) && t.respond_to?(:seeded_path) && t.seeded_path.value
                testname = "#{t.name}_#{t.seed.to_s(10)}"
            else
                testname = t.name
            end
        rescue => e
            $logger.warn e.to_s
            $logger.warn e.backtrace
            $logger.warn t.name
        end

        bid = t.my_host_suite.db_id_pg
        @test_counts[bid] ||= 0
        @test_counts[bid] += 1
        update_test_count(bid, @test_counts[bid])
        t.db_id_pg_tid  = update_test(testname)
        t.db_id_pg_toid = update_testobj(bid, t.db_id_pg_tid)
        test_listed(t)
    end

    def test_listed(t)
        oid = t.db_id_pg_toid
        cid = t.db_id_pg_cid
        aid = t.db_id_pg_aid
        gid = t.db_id_pg_gid

        query = <<EOF
SELECT test_object_run_id FROM #{@table}
    WHERE regression_run_ref = $1 AND test_object_ref = $2
EOF
torid, = select_first(query, @rrid, oid)
if !torid
    insert = <<EOF
INSERT INTO #{@table}
    (test_object_run_id, regression_run_ref, test_object_ref,
    test_status_ref, arch_ref, conf_ref, test_group_ref, start_time)
    VALUES (nextval('test_object_run_id_seq'), $1, $2, $3, $4, $5, $6, $7)
EOF
execute(insert, @rrid, oid, @tsmap['listed'], aid, cid, gid, Time.now.ctime)
torid, = select_first(query, @rrid, oid)
end
t.db_id_pg_torid = torid
    end

    # actor.run invoked
    def test_status(t, status)
        test_found(t) if !t.respond_to?(:db_id_pg_torid)
        rid = t.db_id_pg_torid
        query = <<EOF
UPDATE #{@table}
    SET test_status_ref = $1  WHERE test_object_run_id = $2 AND regression_run_ref = $3
EOF
execute(query, @tsmap[status], rid, @rrid)
    end

    def test_seed(t)
        execute("UPDATE #{@table} SET random_seed=$1 WHERE test_object_run_id=$2", t.seed.value, t.db_id_pg_torid)
    end

    def test_complete(t, status, cpu, sim, warn, error, host, failjob, goldfail)
        oid = t.db_id_pg_toid
        rid = t.db_id_pg_torid
        aid = t.db_id_pg_aid

        query = <<EOF
UPDATE #{@table}
    SET test_status_ref = $1, end_time = $2, cpu_time = $3, sim_time = $4,
    num_warning = $5, num_error = $6, host = $7, gold_failed = $8,
    failed_job_run_ref = $9
        WHERE test_object_run_id = $10 AND regression_run_ref = $11
EOF
execute(query, @tsmap[status], Time.now.ctime, cpu, sim,
        warn, error, host, goldfail, failjob,
        rid, @rrid)
    end

    def kill_outstanding_tests
        $logger.info 'Marking outstanding tests as killed'
        query = <<EOF
UPDATE #{@table} SET test_status_ref=#{@tsmap['killed']} WHERE regression_run_ref=#{@rrid} and
         test_status_ref not in (
        #{@tsmap['killed']},
        #{@tsmap['broken']},
        #{@tsmap['passed']},
        #{@tsmap['finished']},
        #{@tsmap['failed']},
        #{@tsmap['no_output']},
        #{@tsmap['timeout']})
EOF
        execute(query)
    end


    def job_complete(node, start_time, end_time)
        query = <<EOF
UPDATE job.job_run_#{@rrid} SET
     job_run_name=$2, status=$3, host=$4, num_warning=$5,
     num_error=$6, start_time=$7, end_time=$8, cpu_time=$9
     where job_run_id=$1
EOF
        status = node.exception ? -1 : 0

        # TODO
        execute(query, node.db_id_pg_jrid, node.comp_action_args.gsub(/\([^\)]*\)$/, ''), status, "not implemented", 0, 0, start_time, end_time, 0)
    end

    def new_job(node)
        query = "INSERT INTO job.job_run_#{@rrid} (job_run_name) VALUES ($1) RETURNING job_run_id"
        node.db_id_pg_jrid, = select_all(query, node.comp_action).first
    end

    def new_cmd(node)
        cmd_spec = node.cmd_spec
        query = <<EOF
INSERT INTO job.job_cmd_#{@rrid}
        (job_cmd_id, job_run_ref, cmd)
        VALUES (nextval('job_cmd_#{@rrid}_id_seq'), $1, $2) RETURNING job_cmd_id
EOF
        cmd_spec[:db_id_pg_jcid], = select_all(query, node.db_id_pg_jrid, cmd_spec[:cmd]).first
        @db_id_pg_jcid = cmd_spec[:db_id_pg_jcid]
    end

    def cmd_started(node, cmd_spec, time)
        query = <<EOF
UPDATE job.job_cmd_#{@rrid}
    SET host=$1, gcf_id=$2, start_time=$3
    WHERE job_cmd_id=$4
EOF
        execute(query, cmd_spec[:host], cmd_spec[:gcf_id], time, cmd_spec[:db_id_pg_jcid])
    end

    def cmd_done(node, cmd_spec, time)
        unless node.db_id_pg_jrid
            new_job(node)
        end
        query = <<EOF
UPDATE job.job_cmd_#{@rrid}
    SET log_file=$1, exit_code=$2, end_time=$3
    WHERE job_cmd_id=$4
EOF
        execute(query, cmd_spec[:log_file], cmd_spec[:exit_code], time, cmd_spec[:db_id_pg_jcid])
    end

    def update_mem_usage(t, peak_kB, req_MB)
        $logger.info "regression_db_pg: set mem_usage=#{peak_kB} lsf_req_MB=#{req_MB} for id #{t.db_id_pg_torid}"
        execute("UPDATE #{@table} SET mem_usage=$1 WHERE test_object_run_id=$2", peak_kB, t.db_id_pg_torid)
        execute("UPDATE #{@table} SET \"lsf_req_MB\"=$1 WHERE test_object_run_id=$2", req_MB, t.db_id_pg_torid)
    end

    def regression_complete(failure=false)
        query = <<EOF
SELECT test_status_name FROM #{@table}
INNER JOIN test_status ON test_status_id = test_status_ref
WHERE regression_run_ref = #{@rrid}
ORDER BY CASE WHEN test_status_name = 'killed' THEN 1 WHEN test_status_name = 'failed' THEN 2 ELSE 3 END
EOF
        status_name, = select_first(query)
        status_name = "failed" if failure
        status_name ||= "unknown"
        status, = select_first("SELECT regression_status_id FROM regression_status WHERE regression_status_name = '#{status_name}'")

        execute('UPDATE regression_run SET regression_status = $1, end_time = $2 WHERE regression_run_id = $3', status, Time.now.ctime, @rrid)
        execute("DROP  SEQUENCE job_cmd_#{@rrid}_id_seq") if !Dj.is_lite_mode?
    end

    def map_jobs_to_test(jrids, ntt)
        if @pg_ver_major >= 8 && @pg_ver_minor > 2
            torid = [ntt.db_id_pg_torid] * jrids.size
            if jrids.size == 0
                return
            end
            values = torid.zip(jrids).collect do |a,b|
                "(#{a}, #{b})"
            end.join(',')
            query = "INSERT INTO job.test_job_map_#{@rrid} (test_object_run_ref, job_run_ref) VALUES #{values}"
            # Don't use regular execute since there's no point preparing this statement
            @db.async_exec(query) do |res|
	    end
        else
            jrids.each do |jrid|
                values = "(#{ntt.db_id_pg_torid}, #{jrid})"
                query = "INSERT INTO job.test_job_map_#{@rrid} (test_object_run_ref, job_run_ref) VALUES #{values}"
                # Don't use regular execute since there's no point preparing this statement
                @db.async_exec(query) do |res|
		end
            end
        end
    end

    def update_lastpass(rid, oid, cid)
        query = nil
        if @lastpass
            query = <<END
SELECT test_object_ref
        FROM last_pass
        WHERE test_object_ref = $1 AND conf_ref = $2
END
            res, = select_first(query, oid, cid)
            if res
                query = <<END
UPDATE last_pass
        SET test_object_run_ref = $1
        WHERE test_object_ref = $2 AND conf_ref = $3
END
                execute(query, rid, oid, cid)
            else
                query = <<END
INSERT INTO last_pass
        (test_object_run_ref, test_object_ref, conf_ref)
        VALUES ($1, $2, $3)
END
                execute(query, rid, oid, cid)
            end
            query = <<END
UPDATE test_object
    SET last_run_test_object_run_ref = $1
    WHERE test_object_id = $2
END
            execute(query, rid, oid)
        else
            query = <<END
UPDATE test_object
    SET last_run_test_object_run_ref = $1,
        last_pass_test_object_run_ref = $2
    WHERE test_object_id = $3
END
            execute(query, rid, rid, oid)
        end
    end

    def update_block(block)
        if @blockmap.has_key?(block)
            @blockmap[block]
        else
            query = 'SELECT block_id FROM block WHERE block_name = $1'
            insert = <<END
INSERT INTO block
    (block_id, block_name, category_ref, valid)
    VALUES (nextval('block_id_seq'), $1, 0, TRUE)
END
            @blockmap[block] = update_names(query, insert, block)
        end
    end

    def update_conf(conf)
        return if !conf
        if @confmap.has_key?(conf)
            @confmap[conf]
        else
            query = 'SELECT conf_id FROM conf WHERE conf_name = $1'
            insert = <<END
INSERT INTO conf (conf_id, conf_name, valid)
    VALUES (nextval('conf_id_seq'), $1, TRUE)
END
            @confmap[conf] = update_names(query, insert, conf.to_s)
        end
    end

    def update_test(*args)
        query = 'SELECT test_id FROM test WHERE test_name = $1'
        insert = <<END
INSERT INTO test
    (test_id, test_name, valid)
    VALUES (nextval('test_id_seq'), $1, TRUE)
END
        update_names(query, insert, *args)
    end

    def update_arch(arch)
        if @archmap.has_key?(arch)
            @archmap[arch]
        else
            query = 'SELECT arch_id FROM arch WHERE arch_name = $1'
            insert = <<END
INSERT INTO arch
    (arch_id, arch_name, valid)
    VALUES (nextval('arch_id_seq'), $1, TRUE)
END
            @archmap[arch] = update_names(query, insert, arch)
        end
    end

    def update_group(group)
        if @groupmap.has_key?(group)
            @groupmap[group]
        else
            query = 'SELECT test_group_id FROM test_group WHERE test_group_name = $1'
            insert = <<END
INSERT INTO test_group
    (test_group_id, test_group_name, valid)
    VALUES (nextval('test_group_id_seq'), $1, TRUE)
END
            @groupmap[group] = update_names(query, insert, group)
        end
    end

    def update_names(query, insert, *keys)
        qid, = select_first(query, *keys)
        unless qid
            execute(insert, *keys)
            qid, = select_first(query, *keys)
        end
        Integer(qid)
    end

    def update_total_test_count(bid, count)
        query = <<QUERY
SELECT regression_run_ref, block_ref
FROM block_run
WHERE regression_run_ref = $1 AND block_ref = $2
QUERY
        rr_ref, b_ref = select_first(query, @rrid, bid)
        if rr_ref && b_ref
            query = <<QUERY
UPDATE block_run
SET total_test_count = $1
WHERE regression_run_ref = $2 AND block_ref = $3
QUERY
            execute(query, count, @rrid, bid)
        else
            query = <<QUERY
INSERT INTO block_run
(regression_run_ref, block_ref, test_count, total_test_count)
VALUES ($1, $2, $3, $4)
QUERY
            execute(query, @rrid, bid, 0, count)
        end
    end

    def update_test_count(bid, count)
        query = <<QUERY
SELECT test_count
FROM block_run
WHERE regression_run_ref = $1 AND block_ref = $2
QUERY
        old, = select_first(query, @rrid, bid)
        if old
            if old != count
                query = <<QUERY
UPDATE block_run
SET test_count = $1
WHERE regression_run_ref = $2 AND block_ref = $3
QUERY
                execute(query, count, @rrid, bid)
            end
        else
            query = <<QUERY
INSERT INTO block_run
(regression_run_ref, block_ref, test_count)
VALUES ($1, $2, $3)
QUERY
            execute(query, @rrid, bid, count)
        end
    end

    def update_testobj(*args)
        query = <<EOF
SELECT test_object_id
    FROM test_object
    WHERE project_ref = $1 AND block_ref = $2 AND test_ref = $3
EOF
        insert = <<EOF
INSERT INTO test_object
    (test_object_id, project_ref, block_ref, test_ref)
    VALUES (nextval('test_object_id_seq'), $1, $2, $3)
EOF
        update_names(query, insert, @pid, *args)
    end

    def peek_event
        e = nil
        @mutex.synchronize { e = @events.first }
        e
    end

    def shift_event
        e = nil
        @mutex.synchronize { e = @events.shift }
        e
    end

    def push_custom_event e, data
        @mutex.synchronize { @events << {:event=>e, :data=>data} }
    end

    def start
        while !@logger_thread.stop? && !@started
            Thread.pass
        end
        @logger_thread.run
        @started = true
    end

    def stop
        flush
        @logger_thread.exit
        @db.finish if @db
        @started = false
        "Statistics from regression_db_pg.rb\n#{@stats.to_s}".each_line { |l| $logger.info l.chomp }
    end

    def flush
        if @logger_thread.alive?
            begin
                while @events.size > 0
                    @logger_thread.run
                end
            rescue ThreadError => e
                # ignore thread errors
            end
        end
    end

    def flush_and_exit(failure=false)
        $logger.info "REGRESSION_DB_PG : start flush..."
        if @logger_thread.alive?
            begin
                while @events.size > 0
                    @logger_thread.run
                end
                $logger.info "REGRESSION_DB_PG : finish flush..."
            rescue => e
                $logger.warn "regression_db_pg.rb : #{e}"
            ensure
                begin # regression_complete may fail
                    kill_outstanding_tests if !Dj.is_lite_mode?
                    regression_complete(failure) if !Dj.is_lite_mode?
                rescue => e
                    $logger.warn "regression_db_pg.rb : #{e}"
                ensure # To prevent hangs, ensure that we always stop the logger thread, no matter what happens
                    stop
                end
            end
        end
    end
end
