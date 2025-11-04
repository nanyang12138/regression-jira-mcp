"""
Regression-JIRA MCP Server

Main entry point for the MCP server.
Provides unified PostgreSQL and JIRA tools for regression test analysis.
"""

import os
import json
import sys
from typing import Optional
from mcp.server import Server
from mcp.types import Tool, TextContent
from dotenv import load_dotenv

from .db_queries import RegressionDB
from .jira_client import JiraClient
from .log_analyzer import LogAnalyzer
from .error_matcher import ErrorMatcher
from .utils import extract_keywords_from_test_name
from .security import SecurityError
from .pattern_learner import PatternLearner
from .nlp_utils import get_nlp_processor

# Try to import ML components (optional)
try:
    from .data.feedback_storage import FeedbackStorage
    from .ml.model_training import JiraMatcherModel
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False

# Load environment variables
load_dotenv()

# Initialize server
app = Server("regression-jira-mcp")

# Global instances
db: Optional[RegressionDB] = None
jira: Optional[JiraClient] = None
log_analyzer: Optional[LogAnalyzer] = None
error_matcher: Optional[ErrorMatcher] = None
pattern_learner: Optional[PatternLearner] = None
feedback_storage = None  # Optional ML component
ml_model = None  # Optional ML component


def initialize():
    """Initialize all clients"""
    global db, jira, log_analyzer, error_matcher, pattern_learner, feedback_storage, ml_model
    
    try:
        db = RegressionDB()
        jira = JiraClient()
        log_analyzer = LogAnalyzer(
            max_lines=None,  # Scan entire log file, no limit
            ends_only=None   # Scan entire file, not just ends
        )
        error_matcher = ErrorMatcher()
        pattern_learner = PatternLearner()
        
        # Initialize ML components if available
        if ML_AVAILABLE:
            try:
                feedback_storage = FeedbackStorage()
                ml_model = JiraMatcherModel()
                print("ML components initialized", file=sys.stderr)
            except Exception as e:
                print(f"ML components not available: {e}", file=sys.stderr)
                feedback_storage = None
                ml_model = None
    except Exception as e:
        print(f"Error initializing: {str(e)}", file=sys.stderr)
        raise


# ============================================================================
# PostgreSQL Tools
# ============================================================================

@app.list_tools()
async def list_tools() -> list[Tool]:
    """List all available tools"""
    return [
        Tool(
            name="query_failed_tests",
            description="Query failed tests from PostgreSQL database",
            inputSchema={
                "type": "object",
                "properties": {
                    "regression_run_id": {
                        "type": "integer",
                        "description": "Regression run ID (optional if project/regression names provided)"
                    },
                    "project_name": {
                        "type": "string",
                        "description": "Project name (optional)"
                    },
                    "regression_name": {
                        "type": "string",
                        "description": "Regression name (optional)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results (optional, omit for no limit)"
                    },
                    "include_logs": {
                        "type": "boolean",
                        "description": "Whether to analyze log files (default: true)",
                        "default": True
                    }
                }
            }
        ),
        Tool(
            name="get_test_details",
            description="Get detailed information for a specific test",
            inputSchema={
                "type": "object",
                "properties": {
                    "test_name": {
                        "type": "string",
                        "description": "Test name"
                    },
                    "regression_run_id": {
                        "type": "integer",
                        "description": "Regression run ID (optional)"
                    },
                    "analyze_logs": {
                        "type": "boolean",
                        "description": "Whether to analyze log files (default: true)",
                        "default": True
                    }
                },
                "required": ["test_name"]
            }
        ),
        Tool(
            name="get_regression_summary",
            description="Get summary statistics for a regression run",
            inputSchema={
                "type": "object",
                "properties": {
                    "regression_run_id": {
                        "type": "integer",
                        "description": "Regression run ID"
                    }
                },
                "required": ["regression_run_id"]
            }
        ),
        Tool(
            name="analyze_test_log",
            description="Analyze test log file to extract error information",
            inputSchema={
                "type": "object",
                "properties": {
                    "test_name": {
                        "type": "string",
                        "description": "Test name"
                    },
                    "regression_run_id": {
                        "type": "integer",
                        "description": "Regression run ID"
                    }
                },
                "required": ["test_name", "regression_run_id"]
            }
        ),
        Tool(
            name="search_jira_issues",
            description="Search JIRA issues using JQL query",
            inputSchema={
                "type": "object",
                "properties": {
                    "jql": {
                        "type": "string",
                        "description": "JQL query string"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum results (default: 50)",
                        "default": 50
                    }
                },
                "required": ["jql"]
            }
        ),
        Tool(
            name="search_jira_by_text",
            description="Simple text search in JIRA",
            inputSchema={
                "type": "object",
                "properties": {
                    "search_text": {
                        "type": "string",
                        "description": "Text to search for"
                    },
                    "status_filter": {
                        "type": "string",
                        "description": "Filter by status (e.g., 'Resolved', 'Closed')"
                    },
                    "project_filter": {
                        "type": "string",
                        "description": "Filter by project key"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum results (default: 20)",
                        "default": 20
                    }
                },
                "required": ["search_text"]
            }
        ),
        Tool(
            name="get_jira_issue",
            description="Get detailed information for a specific JIRA issue",
            inputSchema={
                "type": "object",
                "properties": {
                    "issue_key": {
                        "type": "string",
                        "description": "JIRA issue key (e.g., 'PROJ-1234')"
                    },
                    "include_comments": {
                        "type": "boolean",
                        "description": "Include comments (default: true)",
                        "default": True
                    }
                },
                "required": ["issue_key"]
            }
        ),
        Tool(
            name="find_solutions_for_test",
            description="🌟 One-click solution finder: Find JIRA solutions for a failed test",
            inputSchema={
                "type": "object",
                "properties": {
                    "test_name": {
                        "type": "string",
                        "description": "Test name"
                    },
                    "regression_run_id": {
                        "type": "integer",
                        "description": "Regression run ID (optional)"
                    },
                    "max_jira_results": {
                        "type": "integer",
                        "description": "Maximum JIRA results (default: 10)",
                        "default": 10
                    }
                },
                "required": ["test_name"]
            }
        ),
        Tool(
            name="batch_find_solutions",
            description="Batch find JIRA solutions for multiple failed tests",
            inputSchema={
                "type": "object",
                "properties": {
                    "regression_run_id": {
                        "type": "integer",
                        "description": "Regression run ID"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of failed tests to process (default: 10)",
                        "default": 10
                    }
                },
                "required": ["regression_run_id"]
            }
        ),
        Tool(
            name="list_regression_runs",
            description="List recent regression runs",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_name": {
                        "type": "string",
                        "description": "Filter by project name (optional)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum results (optional, omit for no limit)"
                    }
                }
            }
        ),
        Tool(
            name="discover_error_patterns",
            description="Analyze unmatched error logs and auto-discover new error patterns",
            inputSchema={
                "type": "object",
                "properties": {
                    "min_frequency": {
                        "type": "integer",
                        "description": "Minimum occurrence count (default: 3)",
                        "default": 3
                    },
                    "export_code": {
                        "type": "boolean",
                        "description": "Whether to export Python code",
                        "default": False
                    }
                }
            }
        ),
        Tool(
            name="get_pattern_learning_stats",
            description="Get statistics of error pattern learning",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="get_system_health",
            description="Get system health status and quality metrics",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="provide_match_feedback",
            description="Provide feedback on JIRA match quality to improve ML model",
            inputSchema={
                "type": "object",
                "properties": {
                    "test_name": {
                        "type": "string",
                        "description": "Test name"
                    },
                    "jira_key": {
                        "type": "string",
                        "description": "JIRA issue key"
                    },
                    "is_relevant": {
                        "type": "boolean",
                        "description": "Whether the JIRA actually solved the test issue"
                    },
                    "relevance_score": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 5,
                        "description": "Relevance score (1-5, optional)"
                    },
                    "comments": {
                        "type": "string",
                        "description": "Optional additional comments"
                    }
                },
                "required": ["test_name", "jira_key", "is_relevant"]
            }
        ),
        Tool(
            name="train_ml_model",
            description="Train ML model using collected feedback data",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="get_ml_model_status",
            description="Get ML model status and statistics",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls"""
    
    try:
        if name == "query_failed_tests":
            result = await query_failed_tests_tool(arguments)
        elif name == "get_test_details":
            result = await get_test_details_tool(arguments)
        elif name == "get_regression_summary":
            result = await get_regression_summary_tool(arguments)
        elif name == "analyze_test_log":
            result = await analyze_test_log_tool(arguments)
        elif name == "search_jira_issues":
            result = await search_jira_issues_tool(arguments)
        elif name == "search_jira_by_text":
            result = await search_jira_by_text_tool(arguments)
        elif name == "get_jira_issue":
            result = await get_jira_issue_tool(arguments)
        elif name == "find_solutions_for_test":
            result = await find_solutions_for_test_tool(arguments)
        elif name == "batch_find_solutions":
            result = await batch_find_solutions_tool(arguments)
        elif name == "list_regression_runs":
            result = await list_regression_runs_tool(arguments)
        elif name == "discover_error_patterns":
            result = await discover_error_patterns_tool(arguments)
        elif name == "get_pattern_learning_stats":
            result = await get_pattern_learning_stats_tool(arguments)
        elif name == "get_system_health":
            result = await get_system_health_tool(arguments)
        elif name == "provide_match_feedback":
            result = await provide_match_feedback_tool(arguments)
        elif name == "train_ml_model":
            result = await train_ml_model_tool(arguments)
        elif name == "get_ml_model_status":
            result = await get_ml_model_status_tool(arguments)
        else:
            raise ValueError(f"Unknown tool: {name}")
        
        return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]
    
    except SecurityError as e:
        # Handle security violations with clear message
        error_result = {
            "error": "SECURITY_VIOLATION",
            "message": str(e),
            "tool": name,
            "note": "This MCP server has read-only access to the database."
        }
        return [TextContent(type="text", text=json.dumps(error_result, indent=2))]
    
    except Exception as e:
        error_result = {"error": str(e), "tool": name}
        return [TextContent(type="text", text=json.dumps(error_result, indent=2))]


# ============================================================================
# Tool Implementations
# ============================================================================

async def query_failed_tests_tool(args: dict) -> dict:
    """Query failed tests from database"""
    regression_run_id = args.get('regression_run_id')
    project_name = args.get('project_name')
    regression_name = args.get('regression_name')
    limit = args.get('limit', 10)
    include_logs = args.get('include_logs', True)
    
    tests = db.query_failed_tests(
        regression_run_id=regression_run_id,
        project_name=project_name,
        regression_name=regression_name,
        limit=limit
    )
    
    # Optionally analyze logs
    if include_logs and tests:
        for test in tests:
            try:
                log_path = db.get_log_file_path(
                    test['test_object_run_id'],
                    test.get('regression_run_id', regression_run_id)
                )
                if log_path and os.path.exists(log_path):
                    error_sig = log_analyzer.analyze_failure(
                        log_path,
                        test.get('block_name'),
                        test['test_name']
                    )
                    test['error_analysis'] = {
                        'signature': error_sig.signature,
                        'keywords': error_sig.error_keywords,
                        'error_level': error_sig.error_level,
                        'tool': error_sig.tool
                    }
                    test['log_file'] = log_path
            except Exception as e:
                test['error_analysis'] = {'error': str(e)}
    
    return {
        'total_failed': len(tests),
        'regression_run_id': regression_run_id,
        'tests': tests
    }


async def get_test_details_tool(args: dict) -> dict:
    """Get test details with optional log analysis"""
    test_name = args['test_name']
    regression_run_id = args.get('regression_run_id')
    analyze_logs = args.get('analyze_logs', True)
    
    test_info = db.get_test_by_name(
        test_name,
        regression_run_id=regression_run_id
    )
    
    if not test_info:
        return {'error': f'Test {test_name} not found'}
    
    # Get log analysis if requested
    if analyze_logs and test_info.get('failed_job_run_ref'):
        try:
            log_path = db.get_log_file_path(
                test_info['test_object_run_id'],
                test_info['regression_run_id']
            )
            if log_path and os.path.exists(log_path):
                error_sig = log_analyzer.analyze_failure(
                    log_path,
                    test_info.get('block_name'),
                    test_name
                )
                test_info['error_analysis'] = error_sig.to_dict()
                test_info['log_file'] = log_path
        except Exception as e:
            test_info['error_analysis'] = {'error': str(e)}
    
    return test_info


async def get_regression_summary_tool(args: dict) -> dict:
    """Get regression run summary"""
    regression_run_id = args['regression_run_id']
    return db.get_regression_summary(regression_run_id)


async def analyze_test_log_tool(args: dict) -> dict:
    """Analyze test log file"""
    test_name = args['test_name']
    regression_run_id = args['regression_run_id']
    
    # Get test info
    test_info = db.get_test_by_name(test_name, regression_run_id=regression_run_id)
    if not test_info:
        return {'error': f'Test {test_name} not found'}
    
    # Get log file path
    log_path = db.get_log_file_path(
        test_info['test_object_run_id'],
        regression_run_id
    )
    
    if not log_path:
        return {'error': 'Log file path not found in database'}
    
    if not os.path.exists(log_path):
        return {
            'error': 'Log file not accessible',
            'log_path': log_path,
            'note': 'Using test name for keyword extraction',
            'keywords': extract_keywords_from_test_name(test_name)
        }
    
    # Analyze log
    error_sig = log_analyzer.analyze_failure(
        log_path,
        test_info.get('block_name'),
        test_name
    )
    
    return {
        'test_name': test_name,
        'log_file': log_path,
        'analysis': error_sig.to_dict(),
        'log_tail': log_analyzer.get_log_tail(log_path, num_lines=50)
    }


async def search_jira_issues_tool(args: dict) -> dict:
    """Search JIRA issues"""
    jql = args['jql']
    max_results = args.get('max_results', 50)
    
    issues = jira.search_issues(jql, max_results=max_results)
    return {
        'total': len(issues),
        'query': jql,
        'issues': issues
    }


async def search_jira_by_text_tool(args: dict) -> dict:
    """Simple JIRA text search"""
    search_text = args['search_text']
    status_filter = args.get('status_filter')
    project_filter = args.get('project_filter')
    max_results = args.get('max_results', 20)
    
    issues = jira.search_by_text(
        search_text,
        status_filter=status_filter,
        project_filter=project_filter,
        max_results=max_results
    )
    
    return {
        'total': len(issues),
        'search_text': search_text,
        'issues': issues
    }


async def get_jira_issue_tool(args: dict) -> dict:
    """Get JIRA issue details"""
    issue_key = args['issue_key']
    include_comments = args.get('include_comments', True)
    
    issue = jira.get_issue(issue_key, include_comments=include_comments)
    if not issue:
        return {'error': f'Issue {issue_key} not found'}
    
    # Extract solution
    solution = jira.extract_solution_from_issue(issue)
    if solution:
        issue['solution_summary'] = solution
    
    return issue


async def find_solutions_for_test_tool(args: dict) -> dict:
    """
    🌟 ONE-CLICK SOLUTION FINDER
    
    The most powerful tool - combines PostgreSQL query, log analysis,
    and intelligent JIRA matching in one call.
    """
    test_name = args['test_name']
    regression_run_id = args.get('regression_run_id')
    max_jira_results = args.get('max_jira_results', 10)
    
    # Step 1: Get test info from database
    test_info = db.get_test_by_name(test_name, regression_run_id=regression_run_id)
    if not test_info:
        return {'error': f'Test {test_name} not found'}
    
    # Step 2: Analyze log file
    error_keywords = []
    error_signature = ""
    log_analysis = None
    
    if test_info.get('failed_job_run_ref'):
        try:
            log_path = db.get_log_file_path(
                test_info['test_object_run_id'],
                test_info['regression_run_id']
            )
            
            if log_path and os.path.exists(log_path):
                error_sig = log_analyzer.analyze_failure(
                    log_path,
                    test_info.get('block_name'),
                    test_name
                )
                error_keywords = error_sig.error_keywords
                error_signature = error_sig.signature
                log_analysis = error_sig.to_dict()
            else:
                # Fallback to test name keywords
                error_keywords = extract_keywords_from_test_name(test_name)
                error_signature = f"Test {test_name} failed (log not accessible)"
        except Exception as e:
            error_keywords = extract_keywords_from_test_name(test_name)
            error_signature = f"Test {test_name} failed (log analysis error: {str(e)})"
    else:
        error_keywords = extract_keywords_from_test_name(test_name)
        error_signature = f"Test {test_name} failed"
    
    # Step 3: Search JIRA
    jira_results = []
    if error_keywords:
        # Build JQL query
        jql = error_matcher.build_jira_jql(
            keywords=error_keywords[:5],
            status_filter='Resolved'
        )
        
        try:
            jira_results = jira.search_issues(jql, max_results=max_jira_results * 2)
        except Exception as e:
            jira_results = []
    
    # Step 4: Intelligent matching and ranking
    matched_issues = error_matcher.match_jira_issues(
        error_signature,
        error_keywords,
        jira_results,
        min_score=0.3,
        max_results=max_jira_results
    )
    
    # Convert matches to dict
    jira_matches = [match.to_dict() for match in matched_issues]
    
    return {
        'test_info': {
            'test_name': test_name,
            'status': test_info.get('status'),
            'block_name': test_info.get('block_name'),
            'regression_run_id': test_info.get('regression_run_id'),
            'num_errors': test_info.get('num_error'),
            'num_warnings': test_info.get('num_warning')
        },
        'error_analysis': {
            'signature': error_signature,
            'keywords': error_keywords,
            'log_analysis': log_analysis
        },
        'jira_matches': jira_matches,
        'summary': {
            'total_jira_found': len(jira_results),
            'relevant_matches': len(jira_matches),
            'top_match_score': jira_matches[0]['similarity_score'] if jira_matches else 0
        }
    }


async def batch_find_solutions_tool(args: dict) -> dict:
    """Batch find solutions for multiple failed tests"""
    regression_run_id = args['regression_run_id']
    limit = args.get('limit', 10)
    
    # Get failed tests
    failed_tests = db.query_failed_tests(
        regression_run_id=regression_run_id,
        limit=limit
    )
    
    results = []
    tests_with_solutions = 0
    
    for test in failed_tests:
        # Find solutions for each test
        try:
            solution_result = await find_solutions_for_test_tool({
                'test_name': test['test_name'],
                'regression_run_id': regression_run_id,
                'max_jira_results': 5
            })
            
            has_solution = len(solution_result.get('jira_matches', [])) > 0
            if has_solution:
                tests_with_solutions += 1
            
            results.append({
                'test_name': test['test_name'],
                'has_solution': has_solution,
                'jira_matches': solution_result.get('jira_matches', [])[:3],  # Top 3
                'error_keywords': solution_result.get('error_analysis', {}).get('keywords', [])
            })
        except Exception as e:
            results.append({
                'test_name': test['test_name'],
                'has_solution': False,
                'error': str(e)
            })
    
    return {
        'regression_run_id': regression_run_id,
        'total_failed_tests': len(failed_tests),
        'processed': len(results),
        'tests_with_solutions': tests_with_solutions,
        'tests_without_solutions': len(results) - tests_with_solutions,
        'results': results
    }


async def list_regression_runs_tool(args: dict) -> dict:
    """List regression runs"""
    project_name = args.get('project_name')
    limit = args.get('limit')  # None if not provided
    
    runs = db.list_regression_runs(project_name=project_name, limit=limit)
    return {
        'total': len(runs),
        'project_filter': project_name,
        'limit_used': limit,
        'runs': runs
    }


async def discover_error_patterns_tool(args: dict) -> dict:
    """Discover error patterns from unmatched logs"""
    min_freq = args.get('min_frequency', 3)
    export_code = args.get('export_code', False)
    
    result = pattern_learner.analyze_patterns(min_frequency=min_freq)
    
    if export_code and result.get('status') == 'success':
        code = pattern_learner.export_as_python_code(
            result['suggested_patterns']
        )
        result['python_code'] = code
        result['code_file'] = 'suggested_patterns.py'
        result['usage_instructions'] = [
            "1. Review suggested patterns",
            "2. Test regex accuracy",
            "3. Add approved patterns to error_patterns.py",
            "4. Restart MCP server"
        ]
    
    return result


async def get_pattern_learning_stats_tool(args: dict) -> dict:
    """Get pattern learning statistics"""
    return pattern_learner.get_stats()


async def get_system_health_tool(args: dict) -> dict:
    """System health check"""
    from datetime import datetime
    
    health = {
        'timestamp': datetime.now().isoformat(),
        'overall_status': 'healthy',
        'components': {}
    }
    
    # 1. NLP Processor
    try:
        nlp = get_nlp_processor()
        nlp_stats = nlp.get_stats()
        health['components']['nlp'] = {
            'status': 'healthy' if nlp_stats['nltk_available'] else 'degraded',
            'nltk_available': nlp_stats['nltk_available'],
            'fallback_count': nlp_stats['fallback_count'],
            'total_calls': nlp_stats['total_calls']
        }
    except Exception as e:
        health['components']['nlp'] = {
            'status': 'error',
            'error': str(e)
        }
    
    # 2. Pattern Learning
    try:
        pattern_stats = pattern_learner.get_stats()
        health['components']['pattern_learning'] = {
            'status': 'healthy',
            'unmatched_errors_recorded': pattern_stats['total_records']
        }
    except Exception as e:
        health['components']['pattern_learning'] = {
            'status': 'error',
            'error': str(e)
        }
    
    # 3. Database Connection
    try:
        # Simple test query
        test_runs = db.list_regression_runs(limit=1)
        health['components']['database'] = {
            'status': 'healthy',
            'can_query': True
        }
    except Exception as e:
        health['components']['database'] = {
            'status': 'unhealthy',
            'error': str(e)
        }
    
    # 4. JIRA Connection
    try:
        # Test JIRA connection
        if jira and jira.jira:
            health['components']['jira'] = {
                'status': 'healthy',
                'base_url': jira.base_url
            }
        else:
            health['components']['jira'] = {
                'status': 'not_initialized'
            }
    except Exception as e:
        health['components']['jira'] = {
            'status': 'unhealthy',
            'error': str(e)
        }
    
    # 5. ML Model (optional)
    if ML_AVAILABLE and ml_model:
        try:
            model_info = ml_model.get_info()
            feedback_stats = feedback_storage.get_stats() if feedback_storage else {}
            health['components']['ml_model'] = {
                'status': 'trained' if model_info['is_trained'] else 'not_trained',
                'accuracy': model_info.get('accuracy', 'N/A'),
                'feedback_collected': feedback_stats.get('total_feedback', 0),
                'ready_for_training': feedback_stats.get('total_feedback', 0) >= 20
            }
        except Exception as e:
            health['components']['ml_model'] = {
                'status': 'error',
                'error': str(e)
            }
    else:
        health['components']['ml_model'] = {
            'status': 'not_available',
            'message': 'Install scikit-learn to enable ML features'
        }
    
    # Determine overall status
    component_statuses = [c.get('status') for c in health['components'].values() if c.get('status') not in ['not_available', 'not_trained']]
    if 'unhealthy' in component_statuses or 'error' in component_statuses:
        health['overall_status'] = 'degraded'
    elif 'not_initialized' in component_statuses:
        health['overall_status'] = 'partial'
    
    return health


async def provide_match_feedback_tool(args: dict) -> dict:
    """Provide feedback on JIRA match quality"""
    if not ML_AVAILABLE or not feedback_storage:
        return {
            'status': 'unavailable',
            'message': 'ML components not available. Install scikit-learn to enable.'
        }
    
    feedback_id = feedback_storage.add_feedback(
        test_name=args['test_name'],
        jira_key=args['jira_key'],
        is_relevant=args['is_relevant'],
        relevance_score=args.get('relevance_score'),
        comments=args.get('comments', '')
    )
    
    stats = feedback_storage.get_stats()
    
    return {
        'status': 'success',
        'feedback_id': feedback_id,
        'message': 'Thank you for your feedback!',
        'total_feedback': stats['total_feedback'],
        'ready_for_training': stats['total_feedback'] >= 20,
        'note': f"Need {max(0, 20 - stats['total_feedback'])} more feedback to train model" if stats['total_feedback'] < 20 else "Ready to train!"
    }


async def train_ml_model_tool(args: dict) -> dict:
    """Train ML model using feedback data"""
    if not ML_AVAILABLE or not ml_model or not feedback_storage:
        return {
            'status': 'unavailable',
            'message': 'ML components not available. Install scikit-learn to enable.'
        }
    
    training_data = feedback_storage.get_training_data(min_samples=20)
    
    if not training_data:
        stats = feedback_storage.get_stats()
        return {
            'status': 'error',
            'message': f'Insufficient training data (need ≥20, got {stats["total_feedback"]})',
            'total_feedback': stats['total_feedback']
        }
    
    result = ml_model.train(training_data)
    return result


async def get_ml_model_status_tool(args: dict) -> dict:
    """Get ML model status"""
    if not ML_AVAILABLE:
        return {
            'ml_available': False,
            'message': 'ML components not installed. Install scikit-learn to enable.',
            'install_command': 'pip install scikit-learn'
        }
    
    if not ml_model or not feedback_storage:
        return {
            'ml_available': True,
            'ml_initialized': False,
            'message': 'ML components failed to initialize'
        }
    
    model_info = ml_model.get_info()
    feedback_stats = feedback_storage.get_stats()
    
    return {
        'ml_available': True,
        'ml_model': model_info,
        'feedback_data': feedback_stats,
        'training_ready': feedback_stats['total_feedback'] >= 20
    }


# ============================================================================
# Server Lifecycle
# ============================================================================

def main():
    """Main entry point"""
    import asyncio
    from mcp.server.stdio import stdio_server
    
    # Initialize clients
    initialize()
    
    async def run():
        async with stdio_server() as (read_stream, write_stream):
            await app.run(read_stream, write_stream, app.create_initialization_options())
    
    try:
        asyncio.run(run())
    finally:
        # Cleanup
        if db:
            db.close()


if __name__ == "__main__":
    main()
