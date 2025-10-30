"""
Security Module

Provides silent query validation and read-only enforcement.
Only raises exceptions when write operations are attempted.
"""

import re
import logging

logger = logging.getLogger(__name__)


class SecurityError(Exception):
    """Raised when a security violation is detected"""
    pass


class QueryValidator:
    """
    Silent query validator that only blocks write operations.
    
    Users won't know about read-only restrictions until they attempt
    to modify data.
    """
    
    # SQL keywords that indicate write operations
    WRITE_KEYWORDS = [
        'INSERT', 'UPDATE', 'DELETE', 'DROP', 
        'CREATE', 'ALTER', 'TRUNCATE', 'GRANT', 
        'REVOKE', 'REPLACE', 'MERGE', 'EXEC',
        'EXECUTE', 'CALL'
    ]
    
    @staticmethod
    def validate(query: str) -> None:
        """
        Validate that query is read-only.
        
        Raises SecurityError only if write operation is detected.
        Silent for all read operations.
        
        Args:
            query: SQL query to validate
            
        Raises:
            SecurityError: If query contains write operations
        """
        if not query:
            return
        
        query_upper = query.upper().strip()
        
        # Check for write keywords
        for keyword in QueryValidator.WRITE_KEYWORDS:
            # Use word boundary regex to avoid false positives
            pattern = r'\b' + keyword + r'\b'
            if re.search(pattern, query_upper):
                logger.warning(f"Blocked write operation attempt: {keyword}")
                raise SecurityError(
                    f"Database modification not permitted. "
                    f"This MCP server is configured for read-only access. "
                    f"Attempted operation: {keyword}"
                )
        
        # Additional check for dangerous patterns
        dangerous_patterns = [
            r'\bINTO\s+OUTFILE\b',  # File write
            r'\bLOAD\s+DATA\b',     # Data import
            r'\bCOPY\b.*\bFROM\b',  # PostgreSQL COPY
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, query_upper):
                logger.warning(f"Blocked dangerous operation: {pattern}")
                raise SecurityError(
                    f"Database modification not permitted. "
                    f"This MCP server is configured for read-only access."
                )


def validate_query(query: str) -> None:
    """
    Convenience function for query validation.
    
    Args:
        query: SQL query to validate
        
    Raises:
        SecurityError: If query contains write operations
    """
    QueryValidator.validate(query)


class JiraOperationValidator:
    """
    JIRA operation validator - only allows read-only operations.
    
    Uses whitelist-based access control to prevent any modification
    of JIRA data, even if users have valid API tokens.
    """
    
    # ========== Whitelist: Allowed Read-Only Operations ==========
    # These are method names from the JIRA Python library, not our wrapper methods
    
    ALLOWED_OPERATIONS = {
        # === Currently used core methods ===
        'search_issues',      # ✓ Search JIRA issues
        'issue',              # ✓ Get single issue details  
        'comments',           # ✓ Get issue comments
        'project',            # ✓ Get project information
        
        # === Future potentially needed read-only operations ===
        'search_users',       # Search users
        'myself',             # Get current user info
        'fields',             # Get field definitions
        'createmeta',         # Get create metadata (to understand field requirements)
        'editmeta',           # Get edit metadata (to understand editable fields)
        'issue_link_types',   # Get issue link types
        'priorities',         # Get priority list
        'resolutions',        # Get resolution types
        'statuses',           # Get status list
        'versions',           # Get version list
        'components',         # Get component list
        'dashboards',         # Get dashboard list
        'filters',            # Get filters
        'favourite_filters',  # Get favorite filters
        'groups',             # Get user groups
        'applicationroles',   # Get application roles
        'worklogs',           # Get worklogs (read-only)
        'watchers',           # Get watchers list (read-only)
        'votes',              # Get vote info (read-only)
        'projects',           # Get all projects
        'user',               # Get user info
        'transitions',        # Get available transitions (read-only metadata)
    }
    
    # ========== Blacklist: Explicitly Forbidden Modification Operations ==========
    
    FORBIDDEN_OPERATIONS = {
        # === Issue CRUD operations ===
        'create_issue', 'create_issues',
        'update_issue', 'update_issue_field',
        'delete_issue',
        'assign_issue',
        
        # === Comment operations ===
        'add_comment',
        'update_comment', 
        'delete_comment',
        
        # === Attachment operations ===
        'add_attachment',
        'delete_attachment',
        
        # === Workflow operations ===
        'transition_issue',
        
        # === Worklog operations ===
        'add_worklog',
        'update_worklog',
        'delete_worklog',
        
        # === Link operations ===
        'create_issue_link',
        'delete_issue_link',
        
        # === Vote and watch operations ===
        'add_vote', 'remove_vote',
        'add_watcher', 'remove_watcher',
        
        # === Other modification operations ===
        'set_issue_status',
        'add_label',
        'remove_label',
        'add_component',
        'delete_component',
        'create_version',
        'update_version',
        'delete_version',
    }
    
    @staticmethod
    def validate(operation_name: str) -> None:
        """
        Validate that JIRA operation is allowed.
        
        Uses defense-in-depth approach:
        1. Explicitly reject blacklisted operations
        2. Only allow whitelisted operations
        3. Reject anything else by default
        
        Args:
            operation_name: JIRA method name
            
        Raises:
            SecurityError: If operation is forbidden
        """
        # Check blacklist first - explicitly forbidden operations
        if operation_name in JiraOperationValidator.FORBIDDEN_OPERATIONS:
            logger.warning(f"Blocked JIRA modification attempt: {operation_name}")
            raise SecurityError(
                f"JIRA modification not permitted. "
                f"This MCP server is configured for read-only access. "
                f"Attempted operation: {operation_name}"
            )
        
        # Check whitelist - only allowed operations can proceed
        if operation_name not in JiraOperationValidator.ALLOWED_OPERATIONS:
            logger.warning(f"Blocked unknown JIRA operation: {operation_name}")
            raise SecurityError(
                f"JIRA operation '{operation_name}' is not in the allowed operations list. "
                f"This MCP server only allows read-only JIRA access."
            )


def validate_jira_operation(operation_name: str) -> None:
    """
    Convenience function for JIRA operation validation.
    
    Args:
        operation_name: JIRA method name to validate
        
    Raises:
        SecurityError: If operation is not allowed
    """
    JiraOperationValidator.validate(operation_name)