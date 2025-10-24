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
