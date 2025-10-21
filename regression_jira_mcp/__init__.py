"""
Regression-JIRA MCP Server

A Model Context Protocol (MCP) server that integrates PostgreSQL regression test results
with JIRA issue tracking, providing intelligent error analysis and solution matching.
"""

__version__ = "1.0.0"
__author__ = "AMD Verification Team"

from .server import main

__all__ = ["main"]
