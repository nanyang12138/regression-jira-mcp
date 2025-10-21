"""
Database Queries Module

PostgreSQL database interface for regression test results.
Based on the schema from regression_db_pg.rb
"""

import os
import psycopg2
from psycopg2 import pool
from typing import List, Dict, Optional, Tuple
from contextlib import contextmanager


class RegressionDB:
    """
    PostgreSQL database interface for regression test results.
    
    Handles connections, queries, and data retrieval from the regression database.
    """
    
    def __init__(self):
        """Initialize database connection"""
        self.connection_pool = None
        self._connect()
        
        # Cache for table names and mappings
        self._table_cache = {}
        self._status_map = None
    
    def _connect(self):
        """Establish database connection pool"""
        try:
            self.connection_pool = psycopg2.pool.SimpleConnectionPool(
                1, 10,  # min and max connections
                database=os.getenv('PGDATABASE'),
                host=os.getenv('PGHOST'),
                port=int(os.getenv('PGPORT', 5432)),
                user=os.getenv('PGUSER'),
                password=os.getenv('PGPASSWORD')
            )
        except Exception as e:
            raise Exception(f"Failed to connect to PostgreSQL: {str(e)}")
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = self.connection_pool.getconn()
        try:
            yield conn
        finally:
            self.connection_pool.putconn(conn)
    
    def get_status_map(self) -> Dict[str, int]:
        """Get test status name to ID mapping"""
        if self._status_map is not None:
            return self._status_map
        
        self._status_map = {}
        query = "SELECT test_status_name, test_status_id FROM test_status"
        
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query)
                for row in cur.fetchall():
                    self._status_map[row[0]] = int(row[1])
        
        return self._status_map
    
    def get_table_name(self, regression_run_id: int) -> str:
        """
        Get dynamic table name for test_object_run.
        
        Table name format: {project}_{regression}_test_object_run
        
        Args:
            regression_run_id: Regression run ID
            
        Returns:
            Table name (quoted for SQL)
        """
        if regression_run_id in self._table_cache:
            return self._table_cache[regression_run_id]
        
        query = """
        SELECT p.project_name, r.regression_name
        FROM regression_run rr
        JOIN project p ON rr.project_ref = p.project_id
        JOIN regression r ON rr.regression_ref = r.regression_id
        WHERE rr.regression_run_id = %s
        """
        
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (regression_run_id,))
                row = cur.fetchone()
                if not row:
                    raise Exception(f"Regression run {regression_run_id} not found")
                
                project_name, regression_name = row
                table_name = f'"{project_name}_{regression_name}_test_object_run"'
                self._table_cache[regression_run_id] = table_name
                return table_name
    
    def query_failed_tests(
        self,
        regression_run_id: Optional[int] = None,
        project_name: Optional[str] = None,
        regression_name: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict]:
        """
        Query failed tests from database.
        
        Args:
            regression_run_id: Regression run ID (or use project/regression names)
            project_name: Project name (optional if regression_run_id provided)
            regression_name: Regression name (optional if regression_run_id provided)
            limit: Maximum number of results
            
        Returns:
            List of test dictionaries
        """
        # Get regression_run_id if not provided
        if not regression_run_id:
            if project_name and regression_name:
                regression_run_id = self._get_latest_run_id(project_name, regression_name)
            else:
                raise ValueError("Must provide either regression_run_id or both project_name and regression_name")
        
        table_name = self.get_table_name(regression_run_id)
        
        query = f"""
        SELECT 
            tor.test_object_run_id,
            t.test_name,
            b.block_name,
            ts.test_status_name,
            a.arch_name,
            c.conf_name,
            tg.test_group_name,
            tor.start_time,
            tor.end_time,
            tor.cpu_time,
            tor.num_error,
            tor.num_warning,
            tor.host,
            tor.random_seed,
            tor.failed_job_run_ref,
            tor.mem_usage,
            tor.lsf_req_mb as lsf_req_mb
        FROM {table_name} tor
        JOIN test_status ts ON tor.test_status_ref = ts.test_status_id
        JOIN test_object tobj ON tor.test_object_ref = tobj.test_object_id
        JOIN test t ON tobj.test_ref = t.test_id
        JOIN block b ON tobj.block_ref = b.block_id
        JOIN arch a ON tor.arch_ref = a.arch_id
        JOIN conf c ON tor.conf_ref = c.conf_id
        JOIN test_group tg ON tor.test_group_ref = tg.test_group_id
        WHERE tor.regression_run_ref = %s
          AND ts.test_status_name = 'failed'
        ORDER BY tor.end_time DESC
        LIMIT %s
        """
        
        results = []
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (regression_run_id, limit))
                for row in cur.fetchall():
                    results.append({
                        'test_object_run_id': row[0],
                        'test_name': row[1],
                        'block_name': row[2],
                        'status': row[3],
                        'arch': row[4],
                        'conf': row[5],
                        'test_group': row[6],
                        'start_time': str(row[7]) if row[7] else None,
                        'end_time': str(row[8]) if row[8] else None,
                        'cpu_time': row[9],
                        'num_error': row[10],
                        'num_warning': row[11],
                        'host': row[12],
                        'random_seed': row[13],
                        'failed_job_run_ref': row[14],
                        'mem_usage': row[15],
                        'lsf_req_mb': row[16]
                    })
        
        return results
    
    def get_test_by_name(
        self,
        test_name: str,
        regression_run_id: Optional[int] = None,
        project_name: Optional[str] = None,
        regression_name: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Get test details by test name.
        
        Args:
            test_name: Test name to search for
            regression_run_id: Regression run ID (optional)
            project_name: Project name (optional)
            regression_name: Regression name (optional)
            
        Returns:
            Test dictionary or None if not found
        """
        if not regression_run_id:
            if project_name and regression_name:
                regression_run_id = self._get_latest_run_id(project_name, regression_name)
            else:
                # Try to find most recent run with this test
                regression_run_id = self._find_run_with_test(test_name)
        
        if not regression_run_id:
            return None
        
        table_name = self.get_table_name(regression_run_id)
        
        query = f"""
        SELECT 
            tor.test_object_run_id,
            t.test_name,
            b.block_name,
            ts.test_status_name,
            a.arch_name,
            c.conf_name,
            tg.test_group_name,
            tor.start_time,
            tor.end_time,
            tor.cpu_time,
            tor.sim_time,
            tor.num_error,
            tor.num_warning,
            tor.host,
            tor.random_seed,
            tor.failed_job_run_ref,
            tor.mem_usage,
            tor.lsf_req_mb as lsf_req_mb
        FROM {table_name} tor
        JOIN test_status ts ON tor.test_status_ref = ts.test_status_id
        JOIN test_object tobj ON tor.test_object_ref = tobj.test_object_id
        JOIN test t ON tobj.test_ref = t.test_id
        JOIN block b ON tobj.block_ref = b.block_id
        JOIN arch a ON tor.arch_ref = a.arch_id
        JOIN conf c ON tor.conf_ref = c.conf_id
        JOIN test_group tg ON tor.test_group_ref = tg.test_group_id
        WHERE t.test_name = %s
          AND tor.regression_run_ref = %s
        """
        
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (test_name, regression_run_id))
                row = cur.fetchone()
                if not row:
                    return None
                
                return {
                    'test_object_run_id': row[0],
                    'test_name': row[1],
                    'block_name': row[2],
                    'status': row[3],
                    'arch': row[4],
                    'conf': row[5],
                    'test_group': row[6],
                    'start_time': str(row[7]) if row[7] else None,
                    'end_time': str(row[8]) if row[8] else None,
                    'cpu_time': row[9],
                    'sim_time': row[10],
                    'num_error': row[11],
                    'num_warning': row[12],
                    'host': row[13],
                    'random_seed': row[14],
                    'failed_job_run_ref': row[15],
                    'mem_usage': row[16],
                    'lsf_req_mb': row[17],
                    'regression_run_id': regression_run_id
                }
    
    def get_log_file_path(
        self,
        test_object_run_id: int,
        regression_run_id: int
    ) -> Optional[str]:
        """
        Get log file path for a failed test.
        
        Uses failed_job_run_ref to find the log file in job_cmd table.
        
        Args:
            test_object_run_id: Test object run ID
            regression_run_id: Regression run ID
            
        Returns:
            Log file path or None
        """
        table_name = self.get_table_name(regression_run_id)
        
        # First get the failed_job_run_ref
        query = f"""
        SELECT failed_job_run_ref
        FROM {table_name}
        WHERE test_object_run_id = %s
        """
        
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (test_object_run_id,))
                row = cur.fetchone()
                if not row or not row[0]:
                    return None
                
                failed_job_run_ref = row[0]
                
                # Get log file from job_cmd table
                query = f"""
                SELECT log_file
                FROM job.job_cmd_{regression_run_id}
                WHERE job_run_ref = %s
                ORDER BY job_cmd_id DESC
                LIMIT 1
                """
                
                cur.execute(query, (failed_job_run_ref,))
                row = cur.fetchone()
                if row and row[0]:
                    return row[0]
        
        return None
    
    def get_regression_summary(self, regression_run_id: int) -> Dict:
        """
        Get summary statistics for a regression run.
        
        Args:
            regression_run_id: Regression run ID
            
        Returns:
            Summary dictionary
        """
        table_name = self.get_table_name(regression_run_id)
        
        # Get run info
        run_query = """
        SELECT 
            rr.regression_run_id,
            p.project_name,
            r.regression_name,
            rr.changelist,
            rr.iteration,
            rr.start_time,
            rr.end_time,
            rs.regression_status_name,
            rr.username,
            rr.client,
            rr.log_directory
        FROM regression_run rr
        JOIN project p ON rr.project_ref = p.project_id
        JOIN regression r ON rr.regression_ref = r.regression_id
        JOIN regression_status rs ON rr.regression_status = rs.regression_status_id
        WHERE rr.regression_run_id = %s
        """
        
        # Get test statistics
        stats_query = f"""
        SELECT 
            ts.test_status_name,
            COUNT(*) as count
        FROM {table_name} tor
        JOIN test_status ts ON tor.test_status_ref = ts.test_status_id
        WHERE tor.regression_run_ref = %s
        GROUP BY ts.test_status_name
        """
        
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                # Get run info
                cur.execute(run_query, (regression_run_id,))
                run_row = cur.fetchone()
                
                if not run_row:
                    raise Exception(f"Regression run {regression_run_id} not found")
                
                # Get statistics
                cur.execute(stats_query, (regression_run_id,))
                stats_rows = cur.fetchall()
                
                stats_by_status = {row[0]: row[1] for row in stats_rows}
                total_tests = sum(stats_by_status.values())
                passed = stats_by_status.get('passed', 0)
                failed = stats_by_status.get('failed', 0)
                
                pass_rate = (passed / total_tests * 100) if total_tests > 0 else 0
                
                return {
                    'regression_run_id': run_row[0],
                    'project_name': run_row[1],
                    'regression_name': run_row[2],
                    'changelist': run_row[3],
                    'iteration': run_row[4],
                    'start_time': str(run_row[5]) if run_row[5] else None,
                    'end_time': str(run_row[6]) if run_row[6] else None,
                    'status': run_row[7],
                    'username': run_row[8],
                    'client': run_row[9],
                    'log_directory': run_row[10],
                    'statistics': {
                        'total_tests': total_tests,
                        'passed': passed,
                        'failed': failed,
                        'by_status': stats_by_status,
                        'pass_rate': f"{pass_rate:.1f}%"
                    }
                }
    
    def search_tests_by_keyword(
        self,
        keyword: str,
        regression_run_id: Optional[int] = None,
        status_filter: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict]:
        """
        Search tests by keyword in test name.
        
        Args:
            keyword: Keyword to search for
            regression_run_id: Regression run ID (optional)
            status_filter: Filter by status (e.g., 'failed')
            limit: Maximum results
            
        Returns:
            List of matching tests
        """
        if not regression_run_id:
            # Search across all recent runs
            return self._search_tests_all_runs(keyword, status_filter, limit)
        
        table_name = self.get_table_name(regression_run_id)
        
        query = f"""
        SELECT 
            tor.test_object_run_id,
            t.test_name,
            b.block_name,
            ts.test_status_name,
            tor.start_time,
            tor.end_time,
            tor.num_error,
            tor.failed_job_run_ref
        FROM {table_name} tor
        JOIN test_status ts ON tor.test_status_ref = ts.test_status_id
        JOIN test_object tobj ON tor.test_object_ref = tobj.test_object_id
        JOIN test t ON tobj.test_ref = t.test_id
        JOIN block b ON tobj.block_ref = b.block_id
        WHERE tor.regression_run_ref = %s
          AND t.test_name ILIKE %s
        """
        
        params = [regression_run_id, f"%{keyword}%"]
        
        if status_filter:
            query += " AND ts.test_status_name = %s"
            params.append(status_filter)
        
        query += " ORDER BY tor.end_time DESC LIMIT %s"
        params.append(limit)
        
        results = []
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                for row in cur.fetchall():
                    results.append({
                        'test_object_run_id': row[0],
                        'test_name': row[1],
                        'block_name': row[2],
                        'status': row[3],
                        'start_time': str(row[4]) if row[4] else None,
                        'end_time': str(row[5]) if row[5] else None,
                        'num_error': row[6],
                        'failed_job_run_ref': row[7],
                        'regression_run_id': regression_run_id
                    })
        
        return results
    
    def get_job_details(
        self,
        job_run_id: int,
        regression_run_id: int
    ) -> Optional[Dict]:
        """
        Get job run details including command and log file.
        
        Args:
            job_run_id: Job run ID
            regression_run_id: Regression run ID
            
        Returns:
            Job details dictionary or None
        """
        query = f"""
        SELECT 
            jr.job_run_id,
            jr.job_run_name,
            jr.status,
            jr.host,
            jr.start_time,
            jr.end_time,
            jr.cpu_time,
            jr.num_warning,
            jr.num_error
        FROM job.job_run_{regression_run_id} jr
        WHERE jr.job_run_id = %s
        """
        
        cmd_query = f"""
        SELECT 
            jc.job_cmd_id,
            jc.cmd,
            jc.log_file,
            jc.exit_code,
            jc.start_time,
            jc.end_time,
            jc.host
        FROM job.job_cmd_{regression_run_id} jc
        WHERE jc.job_run_ref = %s
        ORDER BY jc.job_cmd_id DESC
        LIMIT 1
        """
        
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                # Get job run info
                cur.execute(query, (job_run_id,))
                job_row = cur.fetchone()
                if not job_row:
                    return None
                
                # Get command info
                cur.execute(cmd_query, (job_run_id,))
                cmd_row = cur.fetchone()
                
                result = {
                    'job_run_id': job_row[0],
                    'job_run_name': job_row[1],
                    'status': job_row[2],
                    'host': job_row[3],
                    'start_time': str(job_row[4]) if job_row[4] else None,
                    'end_time': str(job_row[5]) if job_row[5] else None,
                    'cpu_time': job_row[6],
                    'num_warning': job_row[7],
                    'num_error': job_row[8]
                }
                
                if cmd_row:
                    result['command'] = {
                        'cmd_id': cmd_row[0],
                        'cmd': cmd_row[1],
                        'log_file': cmd_row[2],
                        'exit_code': cmd_row[3],
                        'start_time': str(cmd_row[4]) if cmd_row[4] else None,
                        'end_time': str(cmd_row[5]) if cmd_row[5] else None,
                        'host': cmd_row[6]
                    }
                
                return result
    
    def list_regression_runs(
        self,
        project_name: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict]:
        """
        List recent regression runs.
        
        Args:
            project_name: Filter by project name
            limit: Maximum results
            
        Returns:
            List of regression run summaries
        """
        query = """
        SELECT 
            rr.regression_run_id,
            p.project_name,
            r.regression_name,
            rr.changelist,
            rr.iteration,
            rr.start_time,
            rr.end_time,
            rs.regression_status_name
        FROM regression_run rr
        JOIN project p ON rr.project_ref = p.project_id
        JOIN regression r ON rr.regression_ref = r.regression_id
        JOIN regression_status rs ON rr.regression_status = rs.regression_status_id
        """
        
        params = []
        if project_name:
            query += " WHERE p.project_name = %s"
            params.append(project_name)
        
        query += " ORDER BY rr.start_time DESC LIMIT %s"
        params.append(limit)
        
        results = []
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                for row in cur.fetchall():
                    results.append({
                        'regression_run_id': row[0],
                        'project_name': row[1],
                        'regression_name': row[2],
                        'changelist': row[3],
                        'iteration': row[4],
                        'start_time': str(row[5]) if row[5] else None,
                        'end_time': str(row[6]) if row[6] else None,
                        'status': row[7]
                    })
        
        return results
    
    def _get_latest_run_id(self, project_name: str, regression_name: str) -> Optional[int]:
        """Get the latest regression run ID for project/regression"""
        query = """
        SELECT rr.regression_run_id
        FROM regression_run rr
        JOIN project p ON rr.project_ref = p.project_id
        JOIN regression r ON rr.regression_ref = r.regression_id
        WHERE p.project_name = %s AND r.regression_name = %s
        ORDER BY rr.start_time DESC
        LIMIT 1
        """
        
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (project_name, regression_name))
                row = cur.fetchone()
                return row[0] if row else None
    
    def _find_run_with_test(self, test_name: str) -> Optional[int]:
        """Find most recent regression run containing this test"""
        query = """
        SELECT rr.regression_run_id, rr.start_time
        FROM regression_run rr
        JOIN project p ON rr.project_ref = p.project_id
        JOIN regression r ON rr.regression_ref = r.regression_id
        ORDER BY rr.start_time DESC
        LIMIT 10
        """
        
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query)
                runs = cur.fetchall()
                
                # Check each run for the test
                for run_id, _ in runs:
                    try:
                        table_name = self.get_table_name(run_id)
                        check_query = f"""
                        SELECT tor.regression_run_ref
                        FROM {table_name} tor
                        JOIN test_object tobj ON tor.test_object_ref = tobj.test_object_id
                        JOIN test t ON tobj.test_ref = t.test_id
                        WHERE t.test_name = %s
                        LIMIT 1
                        """
                        cur.execute(check_query, (test_name,))
                        if cur.fetchone():
                            return run_id
                    except Exception:
                        continue
        
        return None
    
    def _search_tests_all_runs(
        self,
        keyword: str,
        status_filter: Optional[str],
        limit: int
    ) -> List[Dict]:
        """Search tests across all recent regression runs"""
        # Get recent runs
        runs = self.list_regression_runs(limit=5)
        
        all_results = []
        for run in runs:
            try:
                results = self.search_tests_by_keyword(
                    keyword,
                    run['regression_run_id'],
                    status_filter,
                    limit
                )
                all_results.extend(results)
            except Exception:
                continue
        
        # Sort by end_time and limit
        all_results.sort(key=lambda x: x.get('end_time', ''), reverse=True)
        return all_results[:limit]
    
    def close(self):
        """Close all database connections"""
        if self.connection_pool:
            self.connection_pool.closeall()
