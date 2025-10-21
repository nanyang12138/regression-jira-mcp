"""
Error Pattern Definitions

Converted from Perl's analyzeFailure function.
Contains all error detection regular expressions and ignore patterns.
"""

import re

# ============================================================================
# IGNORE PATTERNS
# These patterns should be skipped during error analysis
# ============================================================================

IGNORE_PATTERNS = [
    r'UVM_ERROR\s*:\s*0',
    r'UVM_ERROR reports\s+:\s+0',
    r'UVM_FATAL\s*:\s*0',
    r'UVM_FATAL reports\s+:\s+0',
    r'grep UVM_ERROR',
    r'grep UVM_FATAL',
    r'-fail_on_regex.*UVM_(FATAL|ERROR)',
    r'^ERROR Param: unable to open file:',
    r'Dumping state in current store \(Lookup error',
    r'possible error on line',
    r'^perl .*\/check_results\.pl .* -type errors',
    r'^ERROR: File .* is non-zero',
    r'Runtime log has errors in Simulator',
    r'Green Light: no errorflag',
    r'grep ERROR .*\.log',
    r'To reproduce the error using the extracted testcase',
    r'To reproduce the error using the original design',
    r'grep -v "To reproduce the error"',
    r'Your project demotes this error to a warning',
    r'Number of demoted UVM_FATAL reports',
    r'Model will not work properly because atleast one pin is not connected',
    r'grep.*ERROR.*mail.*FAIL',
    r'perl .*\/tb_log_grep\.pl.*ERROR',
    r'FlexNet\s+Licensing\s+(checkout|error)',
    r'error in a future release\s*$',
    # Additional patterns from Perl (emulate special case)
    r': no version information available',
]

# Compile ignore patterns for efficiency
COMPILED_IGNORE_PATTERNS = [re.compile(p, re.IGNORECASE) for p in IGNORE_PATTERNS]

# ============================================================================
# ERROR PATTERNS
# Each pattern includes: pattern (regex), level (severity), pos (identifier)
# Higher level = more severe error
# ============================================================================

ERROR_PATTERNS = [
    # ========================================================================
    # CRITICAL ERRORS (Level 10) - System failures
    # ========================================================================
    {
        'pattern': re.compile(r'SEGMENTATION_FAULT'),
        'level': 10,
        'pos': 'builtin:segfault',
        'description': 'Segmentation fault detected'
    },
    {
        'pattern': re.compile(r'Segmentation fault'),
        'level': 10,
        'pos': 'builtin:segfault',
        'description': 'Segmentation fault'
    },
    {
        'pattern': re.compile(r'core dumped'),
        'level': 10,
        'pos': 'builtin:core_dump',
        'description': 'Core dump occurred'
    },
    {
        'pattern': re.compile(r'Cannot allocate memory'),
        'level': 10,
        'pos': 'builtin:oom',
        'description': 'Out of memory'
    },
    
    # ========================================================================
    # HIGH SEVERITY (Level 9) - UVM/Verification errors
    # ========================================================================
    {
        'pattern': re.compile(r'UVM_ERROR'),
        'level': 9,
        'pos': 'builtin:uvm_error',
        'description': 'UVM error reported'
    },
    {
        'pattern': re.compile(r'UVM_FATAL'),
        'level': 9,
        'pos': 'builtin:uvm_fatal',
        'description': 'UVM fatal error'
    },
    
    # ========================================================================
    # ASSERTION FAILURES (Level 8)
    # ========================================================================
    {
        'pattern': re.compile(r'ASSERTION FAILED(?!.*GcLog\.Assert)'),
        'level': 8,
        'pos': 'builtin:assertion',
        'description': 'Assertion failed'
    },
    {
        'pattern': re.compile(r'Assertion \`.*\' failed\.'),
        'level': 8,
        'pos': 'builtin:assertion',
        'description': 'C assertion failed'
    },
    {
        'pattern': re.compile(r'^sim_vcs: .* Assertion'),
        'level': 8,
        'pos': 'builtin:assertion',
        'description': 'VCS assertion'
    },
    {
        'pattern': re.compile(r'TCORE ASSERT'),
        'level': 8,
        'pos': 'builtin:tcore_assert',
        'description': 'TCORE assertion'
    },
    
    # ========================================================================
    # SYSTEM ERRORS (Level 7)
    # ========================================================================
    {
        'pattern': re.compile(r'symbol lookup error:'),
        'level': 7,
        'pos': 'builtin:symbol_lookup',
        'description': 'Symbol lookup error'
    },
    {
        'pattern': re.compile(r'Error: null object access'),
        'level': 7,
        'pos': 'builtin:null_access',
        'description': 'Null pointer access'
    },
    {
        'pattern': re.compile(r'error: .* No such file or directory'),
        'level': 7,
        'pos': 'builtin:no_file',
        'description': 'File not found'
    },
    {
        'pattern': re.compile(r'diff: .* No such file or directory'),
        'level': 7,
        'pos': 'builtin:no_file',
        'description': 'File not found in diff'
    },
    {
        'pattern': re.compile(r'VCS runtime internal error'),
        'level': 7,
        'pos': 'builtin:vcs_internal',
        'description': 'VCS internal error'
    },
    
    # ========================================================================
    # COMPILATION ERRORS (Level 6)
    # ========================================================================
    {
        'pattern': re.compile(r'make.*\*\*\* .* Stop'),
        'level': 6,
        'pos': 'builtin:make_stop',
        'description': 'Make stopped with error'
    },
    {
        'pattern': re.compile(r'Compilation failed in require'),
        'level': 6,
        'pos': 'builtin:compile_fail',
        'description': 'Compilation failed'
    },
    {
        'pattern': re.compile(r' undeclared \(first use this function\)$'),
        'level': 6,
        'pos': 'builtin:undeclared',
        'description': 'Undeclared identifier'
    },
    {
        'pattern': re.compile(r'^syntax error at '),
        'level': 6,
        'pos': 'builtin:syntax_error',
        'description': 'Syntax error'
    },
    
    # ========================================================================
    # GENERAL ERRORS (Level 5) - Most common error patterns
    # ========================================================================
    {
        'pattern': re.compile(r'[^_|]ERROR[^_]'),
        'level': 5,
        'pos': 'builtin:error_bounded',
        'description': 'ERROR not surrounded by underscore or pipe'
    },
    {
        'pattern': re.compile(r'ERROR(?!_)'),
        'level': 5,
        'pos': 'builtin:error',
        'description': 'Generic ERROR'
    },
    {
        'pattern': re.compile(r'^ERROR'),
        'level': 5,
        'pos': 'builtin:error_start',
        'description': 'Line starts with ERROR'
    },
    {
        'pattern': re.compile(r'Error-'),
        'level': 5,
        'pos': 'builtin:error_dash',
        'description': 'Error with dash'
    },
    {
        'pattern': re.compile(r'Error:'),
        'level': 5,
        'pos': 'builtin:error_colon',
        'description': 'Error with colon'
    },
    {
        'pattern': re.compile(r'\serror(?!s_are_warnings)(?!type)(?!_)(?!log)(?!To reproduce the error using the)'),
        'level': 5,
        'pos': 'builtin:error_word',
        'description': 'Error as word'
    },
    {
        'pattern': re.compile(r'FAIL EXIT'),
        'level': 5,
        'pos': 'builtin:fail_exit',
        'description': 'Failed exit'
    },
    {
        'pattern': re.compile(r'failed: exit status'),
        'level': 5,
        'pos': 'builtin:failed_exit',
        'description': 'Failed with exit status'
    },
    {
        'pattern': re.compile(r'failed: caught signal'),
        'level': 5,
        'pos': 'builtin:failed_signal',
        'description': 'Failed with signal'
    },
    {
        'pattern': re.compile(r'TEST INCOMPLETE'),
        'level': 5,
        'pos': 'builtin:incomplete',
        'description': 'Test incomplete'
    },
    {
        'pattern': re.compile(r'surfexp failed to examine'),
        'level': 5,
        'pos': 'builtin:surfexp',
        'description': 'Surfexp examination failed'
    },
    {
        'pattern': re.compile(r'surfexp failed to expand'),
        'level': 5,
        'pos': 'builtin:surfexp',
        'description': 'Surfexp expansion failed'
    },
    {
        'pattern': re.compile(r'Stack trace follows:'),
        'level': 5,
        'pos': 'builtin:stack_trace',
        'description': 'Stack trace available'
    },
    {
        'pattern': re.compile(r'\*E[^A-Za-z]'),
        'level': 5,
        'pos': 'builtin:star_e',
        'description': 'Error marker *E'
    },
    {
        'pattern': re.compile(r'\*F[^A-Za-z]'),
        'level': 5,
        'pos': 'builtin:star_f',
        'description': 'Fatal marker *F'
    },
    {
        'pattern': re.compile(r'\*\*\* SCV_ERROR: (.*) at time \d+'),
        'level': 5,
        'pos': 'builtin:scv_error',
        'description': 'SCV error'
    },
    {
        'pattern': re.compile(r'SCV_ERROR: CONSTRAINT_ERROR'),
        'level': 5,
        'pos': 'builtin:scv_constraint',
        'description': 'SCV constraint error'
    },
    {
        'pattern': re.compile(r'^OVL_ERROR :'),
        'level': 5,
        'pos': 'builtin:ovl_error',
        'description': 'OVL error'
    },
    {
        'pattern': re.compile(r'^Files .* differ'),
        'level': 5,
        'pos': 'builtin:files_differ',
        'description': 'File comparison failed'
    },
    {
        'pattern': re.compile(r'Mismatch!!!'),
        'level': 5,
        'pos': 'builtin:mismatch',
        'description': 'Value mismatch'
    },
    {
        'pattern': re.compile(r'cmd runtime exceeded timeout'),
        'level': 5,
        'pos': 'builtin:timeout',
        'description': 'Command timeout'
    },
    {
        'pattern': re.compile(r'^Maximum evaluation count'),
        'level': 5,
        'pos': 'builtin:max_eval',
        'description': 'Maximum evaluation count reached'
    },
    {
        'pattern': re.compile(r'still asserted at finish'),
        'level': 5,
        'pos': 'builtin:still_asserted',
        'description': 'Signal still asserted at finish'
    },
    {
        'pattern': re.compile(r'\d+ : fail'),
        'level': 5,
        'pos': 'builtin:numbered_fail',
        'description': 'Numbered failure'
    },
    {
        'pattern': re.compile(r'Error: TC BFM'),
        'level': 5,
        'pos': 'builtin:tc_bfm',
        'description': 'TC BFM error'
    },
    {
        'pattern': re.compile(r'^TCoreCail:'),
        'level': 5,
        'pos': 'builtin:tcorecail',
        'description': 'TCoreCail error'
    },
    
    # ========================================================================
    # TOOL-SPECIFIC ERRORS (Level 4-5)
    # ========================================================================
    {
        'pattern': re.compile(r'run FAILED'),
        'level': 4,
        'pos': 'builtin:run_failed',
        'description': 'Run failed'
    },
    {
        'pattern': re.compile(r'Lint FAILED with Warnings\.Errors', re.IGNORECASE),
        'level': 4,
        'pos': 'builtin:lint_failed',
        'description': 'Lint failed'
    },
    {
        'pattern': re.compile(r'100%:\s*\w+\s*fail:'),
        'level': 4,
        'pos': 'builtin:100pct_fail',
        'description': '100% failure rate'
    },
    {
        'pattern': re.compile(r'^emulate: '),
        'level': 5,
        'pos': 'builtin:emulate',
        'description': 'Emulation error'
    },
    {
        'pattern': re.compile(r'^db_emulate: '),
        'level': 5,
        'pos': 'builtin:db_emulate',
        'description': 'DB emulation error'
    },
    {
        'pattern': re.compile(r'^bia error:'),
        'level': 5,
        'pos': 'builtin:bia_error',
        'description': 'BIA error'
    },
    {
        'pattern': re.compile(r'^cbgen error'),
        'level': 5,
        'pos': 'builtin:cbgen_error',
        'description': 'CBGEN error'
    },
    {
        'pattern': re.compile(r'^cb_emulate'),
        'level': 5,
        'pos': 'builtin:cb_emulate',
        'description': 'CB emulate error'
    },
    {
        'pattern': re.compile(r'mem_diff_dir\.pl FAILED'),
        'level': 5,
        'pos': 'builtin:mem_diff_failed',
        'description': 'Memory diff failed'
    },
    {
        'pattern': re.compile(r'vec_check_dir\.pl FAILED'),
        'level': 5,
        'pos': 'builtin:vec_check_failed',
        'description': 'Vector check failed'
    },
    
    # ========================================================================
    # HARDWARE-SPECIFIC ERRORS
    # ========================================================================
    {
        'pattern': re.compile(r'CP_VGT_START pulse was received'),
        'level': 5,
        'pos': 'builtin:cp_vgt_start',
        'description': 'CP VGT START pulse error'
    },
    {
        'pattern': re.compile(r'Request for more SQ GPRs than supported'),
        'level': 5,
        'pos': 'builtin:sq_gprs',
        'description': 'SQ GPR limit exceeded'
    },
    {
        'pattern': re.compile(r'Request for more SQ Threads than supported'),
        'level': 5,
        'pos': 'builtin:sq_threads',
        'description': 'SQ thread limit exceeded'
    },
    {
        'pattern': re.compile(r'illegal_read_address: started'),
        'level': 5,
        'pos': 'builtin:illegal_read',
        'description': 'Illegal read address'
    },
    {
        'pattern': re.compile(r'mem_framebuf_r not found!'),
        'level': 5,
        'pos': 'builtin:mem_framebuf',
        'description': 'Framebuffer not found'
    },
    {
        'pattern': re.compile(r'tar:.*framebuf.*Not found in archive'),
        'level': 5,
        'pos': 'builtin:framebuf_archive',
        'description': 'Framebuffer not in archive'
    },
    
    # ========================================================================
    # DV/TOOL ERRORS
    # ========================================================================
    {
        'pattern': re.compile(r'dv: can\'t move to '),
        'level': 5,
        'pos': 'builtin:dv_cant_move',
        'description': 'DV cannot move to directory'
    },
    {
        'pattern': re.compile(r'does not match bootstrap parameter'),
        'level': 5,
        'pos': 'builtin:bootstrap_mismatch',
        'description': 'Bootstrap parameter mismatch'
    },
    {
        'pattern': re.compile(r'inferior process received signal'),
        'level': 5,
        'pos': 'builtin:inferior_signal',
        'description': 'Inferior process signal'
    },
    {
        'pattern': re.compile(r'more than .* pct missed overlaps'),
        'level': 5,
        'pos': 'builtin:missed_overlaps',
        'description': 'Too many missed overlaps'
    },
    {
        'pattern': re.compile(r'both exist -- please delete one'),
        'level': 5,
        'pos': 'builtin:duplicate_exists',
        'description': 'Duplicate files exist'
    },
    {
        'pattern': re.compile(r'Error: out of memory while attempting'),
        'level': 5,
        'pos': 'builtin:oom_attempt',
        'description': 'Out of memory during operation'
    },
    {
        'pattern': re.compile(r'The tool has just run out of memory'),
        'level': 5,
        'pos': 'builtin:tool_oom',
        'description': 'Tool out of memory'
    },
    {
        'pattern': re.compile(r'not found -- typo'),
        'level': 5,
        'pos': 'builtin:not_found_typo',
        'description': 'Item not found (typo?)'
    },
    {
        'pattern': re.compile(r'^\s*sim_warnings\.pl:\s*!*Error:'),
        'level': 5,
        'pos': 'builtin:sim_warnings',
        'description': 'Simulation warnings error'
    },
    {
        'pattern': re.compile(r'^db_mem_htile_check\.pl: [1-9]+[0-9]* errors found in checking'),
        'level': 5,
        'pos': 'builtin:htile_check',
        'description': 'H-tile check errors'
    },
]

# Compile all error patterns for efficiency
for pattern_dict in ERROR_PATTERNS:
    if not isinstance(pattern_dict['pattern'], re.Pattern):
        pattern_dict['pattern'] = re.compile(pattern_dict['pattern'])

# ============================================================================
# WARNING PATTERNS (Only used when warnings are treated as errors)
# ============================================================================

WARNING_PATTERNS = [
    {
        'pattern': re.compile(r'warning', re.IGNORECASE),
        'level': 3,
        'pos': 'builtin:warning',
        'description': 'Warning message'
    },
]

# Compile warning patterns
for pattern_dict in WARNING_PATTERNS:
    if not isinstance(pattern_dict['pattern'], re.Pattern):
        pattern_dict['pattern'] = re.compile(pattern_dict['pattern'])
