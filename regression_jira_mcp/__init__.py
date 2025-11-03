"""
Regression-JIRA MCP Server

A Model Context Protocol (MCP) server that integrates PostgreSQL regression test results
with JIRA issue tracking, providing intelligent error analysis and solution matching.

v1.1.0 - Enhanced with NLP, pattern learning, caching, and system health monitoring.
"""

__version__ = "1.1.0"
__author__ = "AMD Verification Team"

# Lazy import to avoid loading MCP dependencies unless actually running the server
__all__ = ["main", "NLPProcessor", "PatternLearner", "CacheManager"]

def _import_main():
    """Lazy import main to avoid MCP dependency"""
    from .server import main
    return main

def __getattr__(name):
    """Lazy attribute access for optional imports"""
    if name == "main":
        return _import_main()
    elif name == "NLPProcessor":
        from .nlp_utils import NLPProcessor
        return NLPProcessor
    elif name == "PatternLearner":
        from .pattern_learner import PatternLearner
        return PatternLearner
    elif name == "CacheManager":
        from .cache_manager import CacheManager
        return CacheManager
    else:
        raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
