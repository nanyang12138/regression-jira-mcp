"""
JIRA Client Module

JIRA API interface for searching and retrieving issue information.
Includes read-only protection layer to prevent data modification.
"""

import os
from typing import List, Dict, Optional
from jira import JIRA
from .utils import create_jira_url, extract_keywords
from .security import validate_jira_operation, SecurityError


class ReadOnlyJiraProxy:
    """
    Read-only proxy wrapper for JIRA client.
    
    Intercepts all method calls to the JIRA library and validates
    that only read-only operations are performed. This provides
    defense-in-depth security even if users have valid API tokens.
    
    Implementation uses __getattr__ to intercept method access and
    validate operations before forwarding to the underlying JIRA instance.
    """
    
    def __init__(self, jira_instance):
        """
        Initialize proxy with JIRA instance.
        
        Args:
            jira_instance: The underlying JIRA client instance to wrap
        """
        # Use object.__setattr__ to avoid triggering our custom __setattr__
        object.__setattr__(self, '_jira', jira_instance)
    
    def __getattr__(self, name):
        """
        Intercept all attribute/method access.
        
        Validates that the requested operation is read-only before
        forwarding to the underlying JIRA instance.
        
        Args:
            name: Name of the attribute/method being accessed
            
        Returns:
            The requested attribute/method from underlying JIRA instance
            
        Raises:
            SecurityError: If operation is not allowed
        """
        # Validate operation is allowed
        validate_jira_operation(name)
        
        # Return the actual method/attribute from underlying JIRA instance
        return getattr(self._jira, name)
    
    def __setattr__(self, name, value):
        """
        Block attribute modification (except internal _jira).
        
        Args:
            name: Attribute name
            value: Attribute value
            
        Raises:
            SecurityError: If attempting to modify non-internal attributes
        """
        if name != '_jira':
            raise SecurityError(
                "Cannot modify JIRA client attributes. "
                "This MCP server has read-only access."
            )
        object.__setattr__(self, name, value)


class JiraClient:
    """
    JIRA API client wrapper with read-only protection.
    
    Provides simplified interface to JIRA Cloud for searching issues,
    getting issue details, and extracting solutions.
    
    All JIRA operations are wrapped with ReadOnlyJiraProxy to ensure
    only read-only operations are permitted, even with valid API tokens.
    """
    
    def __init__(self):
        """Initialize JIRA client with read-only protection"""
        self._raw_jira = None  # Original JIRA instance (not exposed)
        self.jira = None       # Read-only proxy wrapper (used by all methods)
        self.base_url = os.getenv('JIRA_URL', '')
        self._connect()
    
    def _connect(self):
        """Establish JIRA connection with read-only wrapper"""
        try:
            # Create the underlying JIRA connection
            self._raw_jira = JIRA(
                server=self.base_url,
                basic_auth=(
                    os.getenv('JIRA_USERNAME'),
                    os.getenv('JIRA_API_TOKEN')
                )
            )
            
            # Wrap with read-only proxy for security
            # All method calls will be validated before reaching JIRA library
            self.jira = ReadOnlyJiraProxy(self._raw_jira)
            
        except Exception as e:
            raise Exception(f"Failed to connect to JIRA: {str(e)}")
    
    def search_issues(
        self,
        jql: str,
        max_results: int = 50,
        fields: Optional[List[str]] = None
    ) -> List[Dict]:
        """
        Search JIRA issues using JQL.
        
        Args:
            jql: JQL query string
            max_results: Maximum results to return
            fields: Fields to retrieve (None = default fields)
            
        Returns:
            List of issue dictionaries
        """
        if fields is None:
            fields = ['summary', 'status', 'description', 'resolution', 
                     'created', 'updated', 'assignee', 'labels', 'components']
        
        try:
            issues = self.jira.search_issues(jql, maxResults=max_results, fields=','.join(fields))
            
            results = []
            for issue in issues:
                issue_dict = self._issue_to_dict(issue)
                results.append(issue_dict)
            
            return results
        
        except Exception as e:
            raise Exception(f"JIRA search failed: {str(e)}")
    
    def search_by_text(
        self,
        search_text: str,
        status_filter: Optional[str] = None,
        project_filter: Optional[str] = None,
        max_results: int = 20
    ) -> List[Dict]:
        """
        Simple text search in JIRA.
        
        Args:
            search_text: Text to search for
            status_filter: Filter by status (e.g., "Resolved", "Closed")
            project_filter: Filter by project key
            max_results: Maximum results
            
        Returns:
            List of issue dictionaries
        """
        # Build JQL query
        jql_parts = [f'text ~ "{search_text}"']
        
        if project_filter:
            jql_parts.append(f'project = {project_filter}')
        
        if status_filter:
            if status_filter.lower() == 'resolved':
                jql_parts.append('status IN (Resolved, Closed)')
            else:
                jql_parts.append(f'status = {status_filter}')
        
        jql = ' AND '.join(jql_parts)
        return self.search_issues(jql, max_results)
    
    def get_issue(
        self,
        issue_key: str,
        include_comments: bool = True
    ) -> Optional[Dict]:
        """
        Get detailed information for a specific JIRA issue.
        
        Args:
            issue_key: JIRA issue key (e.g., "PROJ-1234")
            include_comments: Whether to include comments
            
        Returns:
            Issue dictionary or None if not found
        """
        try:
            issue = self.jira.issue(issue_key)
            issue_dict = self._issue_to_dict(issue)
            
            if include_comments:
                comments = self.jira.comments(issue_key)
                issue_dict['comments'] = [
                    {
                        'id': comment.id,
                        'author': comment.author.displayName if hasattr(comment.author, 'displayName') else str(comment.author),
                        'body': comment.body,
                        'created': str(comment.created)
                    }
                    for comment in comments
                ]
            
            return issue_dict
        
        except Exception:
            return None
    
    def get_comments(self, issue_key: str) -> List[Dict]:
        """
        Get all comments for an issue.
        
        Args:
            issue_key: JIRA issue key
            
        Returns:
            List of comment dictionaries
        """
        try:
            comments = self.jira.comments(issue_key)
            return [
                {
                    'id': comment.id,
                    'author': comment.author.displayName if hasattr(comment.author, 'displayName') else str(comment.author),
                    'body': comment.body,
                    'created': str(comment.created),
                    'updated': str(comment.updated) if hasattr(comment, 'updated') else None
                }
                for comment in comments
            ]
        except Exception as e:
            return []
    
    def search_by_labels(
        self,
        labels: List[str],
        match_all: bool = False,
        max_results: int = 20
    ) -> List[Dict]:
        """
        Search JIRA issues by labels.
        
        Args:
            labels: List of labels to search for
            match_all: If True, match all labels; if False, match any
            max_results: Maximum results
            
        Returns:
            List of issue dictionaries
        """
        if not labels:
            return []
        
        if match_all:
            # All labels must match
            label_parts = [f'labels = "{label}"' for label in labels]
            jql = ' AND '.join(label_parts)
        else:
            # Any label matches
            label_parts = [f'labels = "{label}"' for label in labels]
            jql = ' OR '.join(label_parts)
        
        return self.search_issues(jql, max_results)
    
    def get_related_issues(self, issue_key: str) -> List[Dict]:
        """
        Get issues related to the specified issue.
        
        Args:
            issue_key: JIRA issue key
            
        Returns:
            List of related issue dictionaries
        """
        try:
            issue = self.jira.issue(issue_key)
            related = []
            
            # Get issue links
            if hasattr(issue.fields, 'issuelinks'):
                for link in issue.fields.issuelinks:
                    related_issue = None
                    relation_type = None
                    
                    if hasattr(link, 'outwardIssue'):
                        related_issue = link.outwardIssue
                        relation_type = link.type.outward if hasattr(link.type, 'outward') else 'relates to'
                    elif hasattr(link, 'inwardIssue'):
                        related_issue = link.inwardIssue
                        relation_type = link.type.inward if hasattr(link.type, 'inward') else 'relates to'
                    
                    if related_issue:
                        related.append({
                            'key': related_issue.key,
                            'summary': related_issue.fields.summary if hasattr(related_issue.fields, 'summary') else '',
                            'status': str(related_issue.fields.status) if hasattr(related_issue.fields, 'status') else 'Unknown',
                            'relation': relation_type,
                            'link': create_jira_url(self.base_url, related_issue.key)
                        })
            
            return related
        
        except Exception:
            return []
    
    def get_project_info(self, project_key: str) -> Optional[Dict]:
        """
        Get JIRA project information.
        
        Args:
            project_key: Project key (e.g., "PROJ")
            
        Returns:
            Project dictionary or None
        """
        try:
            project = self.jira.project(project_key)
            return {
                'key': project.key,
                'name': project.name,
                'description': project.description if hasattr(project, 'description') else None,
                'lead': project.lead.displayName if hasattr(project.lead, 'displayName') else str(project.lead),
                'url': create_jira_url(self.base_url, project.key)
            }
        except Exception:
            return None
    
    def extract_solution_from_issue(self, issue_dict: Dict) -> Optional[str]:
        """
        Extract solution/fix information from JIRA issue.
        
        Looks for solution-related keywords in description and comments.
        
        Args:
            issue_dict: Issue dictionary
            
        Returns:
            Solution summary or None
        """
        solution_keywords = ['solution', 'fix', 'resolved', 'patch', 'workaround', 
                           'applied', 'implemented', 'corrected', 'updated']
        
        # Check resolution
        if issue_dict.get('resolution'):
            resolution = issue_dict['resolution'].lower()
            if resolution in ['fixed', 'done', 'resolved']:
                # Look in comments
                if issue_dict.get('comments'):
                    for comment in issue_dict['comments']:
                        body = comment.get('body', '').lower()
                        for keyword in solution_keywords:
                            if keyword in body:
                                # Extract sentences with solution keywords
                                sentences = comment.get('body', '').split('.')
                                for sentence in sentences:
                                    if any(kw in sentence.lower() for kw in solution_keywords):
                                        return sentence.strip()[:200]
                
                # Check description
                if issue_dict.get('description'):
                    desc = issue_dict['description']
                    sentences = desc.split('.')
                    for sentence in sentences:
                        if any(kw in sentence.lower() for kw in solution_keywords):
                            return sentence.strip()[:200]
        
        return None
    
    def _issue_to_dict(self, issue) -> Dict:
        """
        Convert JIRA issue object to dictionary.
        
        Args:
            issue: JIRA issue object
            
        Returns:
            Dictionary representation
        """
        fields = issue.fields
        
        return {
            'key': issue.key,
            'summary': fields.summary if hasattr(fields, 'summary') else '',
            'description': fields.description if hasattr(fields, 'description') else '',
            'status': str(fields.status) if hasattr(fields, 'status') else 'Unknown',
            'resolution': str(fields.resolution) if hasattr(fields, 'resolution') and fields.resolution else None,
            'priority': str(fields.priority) if hasattr(fields, 'priority') and fields.priority else None,
            'created': str(fields.created) if hasattr(fields, 'created') else None,
            'updated': str(fields.updated) if hasattr(fields, 'updated') else None,
            'assignee': fields.assignee.displayName if hasattr(fields, 'assignee') and fields.assignee else None,
            'reporter': fields.reporter.displayName if hasattr(fields, 'reporter') and fields.reporter else None,
            'labels': list(fields.labels) if hasattr(fields, 'labels') else [],
            'components': [c.name for c in fields.components] if hasattr(fields, 'components') else [],
            'fix_versions': [v.name for v in fields.fixVersions] if hasattr(fields, 'fixVersions') else [],
            'link': create_jira_url(self.base_url, issue.key)
        }
