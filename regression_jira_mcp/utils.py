"""
Utility Functions

Helper functions for keyword extraction, text processing, and other utilities.
"""

import re
from typing import List, Set
from dataclasses import dataclass


# Common noise words to filter out from keyword extraction
NOISE_WORDS = {
    'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
    'of', 'with', 'by', 'from', 'as', 'is', 'was', 'were', 'are', 'be',
    'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
    'would', 'should', 'could', 'may', 'might', 'must', 'can', 'this',
    'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they',
    'what', 'which', 'who', 'when', 'where', 'why', 'how', 'all', 'each',
    'every', 'both', 'few', 'more', 'most', 'other', 'some', 'such', 'no',
    'nor', 'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very', 's',
    't', 'just', 'don', 'now', 've', 'll', 'm', 'o', 're', 'd', 'y'
}


def extract_keywords(text: str, max_keywords: int = 10) -> List[str]:
    """
    Extract meaningful keywords from text for JIRA searching.
    
    Args:
        text: Input text to extract keywords from
        max_keywords: Maximum number of keywords to return
        
    Returns:
        List of extracted keywords
    """
    if not text:
        return []
    
    # Convert to lowercase
    text = text.lower()
    
    # Extract words (alphanumeric sequences)
    words = re.findall(r'\b[a-z0-9_]+\b', text)
    
    # Filter out noise words and short words
    keywords = []
    seen = set()
    
    for word in words:
        # Skip if already seen, too short, or is noise
        if word in seen or len(word) <= 2 or word in NOISE_WORDS:
            continue
        
        # Skip pure numbers unless they look like error codes
        if word.isdigit() and len(word) < 3:
            continue
            
        seen.add(word)
        keywords.append(word)
        
        if len(keywords) >= max_keywords:
            break
    
    return keywords


def extract_keywords_from_test_name(test_name: str) -> List[str]:
    """
    Extract keywords from a test name using naming conventions.
    
    Examples:
        test_memory_allocation -> ['memory', 'allocation']
        test_dma_transfer_basic -> ['dma', 'transfer', 'basic']
        
    Args:
        test_name: Test name
        
    Returns:
        List of extracted keywords
    """
    if not test_name:
        return []
    
    # Remove common test prefixes
    name = test_name.lower()
    for prefix in ['test_', 'tc_', 'testcase_']:
        if name.startswith(prefix):
            name = name[len(prefix):]
            break
    
    # Split on underscores and camelCase
    # First handle camelCase
    name = re.sub('([a-z])([A-Z])', r'\1_\2', name)
    
    # Split on underscores
    parts = name.split('_')
    
    # Filter meaningful parts
    keywords = []
    for part in parts:
        part = part.strip()
        if len(part) > 2 and part not in NOISE_WORDS:
            keywords.append(part)
    
    return keywords


def clean_text_for_comparison(text: str) -> str:
    """
    Clean text for similarity comparison.
    
    Args:
        text: Input text
        
    Returns:
        Cleaned text
    """
    if not text:
        return ""
    
    # Convert to lowercase
    text = text.lower()
    
    # Remove special characters but keep spaces
    text = re.sub(r'[^a-z0-9\s]', ' ', text)
    
    # Normalize whitespace
    text = ' '.join(text.split())
    
    return text


def truncate_text(text: str, max_length: int = 100) -> str:
    """
    Truncate text to maximum length with ellipsis.
    
    Args:
        text: Input text
        max_length: Maximum length
        
    Returns:
        Truncated text
    """
    if not text:
        return ""
    
    if len(text) <= max_length:
        return text
    
    return text[:max_length-3] + "..."


def format_time_duration(seconds: float) -> str:
    """
    Format time duration in human-readable format.
    
    Args:
        seconds: Duration in seconds
        
    Returns:
        Formatted string like "1h 30m 45s"
    """
    if seconds < 60:
        return f"{seconds:.1f}s"
    
    minutes = int(seconds // 60)
    remaining_seconds = int(seconds % 60)
    
    if minutes < 60:
        return f"{minutes}m {remaining_seconds}s"
    
    hours = int(minutes // 60)
    remaining_minutes = int(minutes % 60)
    
    return f"{hours}h {remaining_minutes}m {remaining_seconds}s"


def safe_get_dict_value(d: dict, *keys, default=None):
    """
    Safely get nested dictionary values.
    
    Args:
        d: Dictionary to query
        *keys: Sequence of keys to traverse
        default: Default value if key not found
        
    Returns:
        Value or default
        
    Example:
        safe_get_dict_value(data, 'test', 'error', 'message', default='unknown')
    """
    value = d
    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return default
    return value


def parse_jql_for_keywords(jql: str) -> List[str]:
    """
    Extract search keywords from a JQL query.
    
    Args:
        jql: JQL query string
        
    Returns:
        List of keywords found in the query
    """
    keywords = []
    
    # Look for text search patterns: text ~ "keyword"
    text_matches = re.findall(r'text\s*~\s*["\']([^"\']+)["\']', jql, re.IGNORECASE)
    for match in text_matches:
        keywords.extend(match.split())
    
    # Look for summary search: summary ~ "keyword"
    summary_matches = re.findall(r'summary\s*~\s*["\']([^"\']+)["\']', jql, re.IGNORECASE)
    for match in summary_matches:
        keywords.extend(match.split())
    
    return list(set(keywords))  # Remove duplicates


def estimate_token_count(text: str) -> int:
    """
    Rough estimate of token count for text.
    Useful for staying within API limits.
    
    Args:
        text: Input text
        
    Returns:
        Estimated token count
    """
    if not text:
        return 0
    
    # Rough approximation: 1 token ≈ 4 characters
    return len(text) // 4


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a string to be safe for use as a filename.
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename
    """
    # Remove or replace invalid characters
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    
    # Limit length
    if len(filename) > 200:
        filename = filename[:200]
    
    return filename


def create_jira_url(base_url: str, issue_key: str) -> str:
    """
    Create full JIRA issue URL from base URL and issue key.
    
    Args:
        base_url: JIRA base URL (e.g., https://amd.atlassian.net)
        issue_key: Issue key (e.g., PROJ-1234)
        
    Returns:
        Full URL to the issue
    """
    # Remove trailing slash from base URL
    base_url = base_url.rstrip('/')
    
    return f"{base_url}/browse/{issue_key}"


@dataclass
class SimilarityScore:
    """Container for similarity comparison results"""
    score: float  # 0.0 to 1.0
    matching_keywords: List[str]
    total_keywords: int
    
    def __str__(self):
        percentage = int(self.score * 100)
        return f"{percentage}% match ({len(self.matching_keywords)}/{self.total_keywords} keywords)"


def calculate_keyword_similarity(keywords1: List[str], keywords2: List[str]) -> SimilarityScore:
    """
    Calculate similarity between two sets of keywords.
    
    Args:
        keywords1: First set of keywords
        keywords2: Second set of keywords
        
    Returns:
        SimilarityScore object
    """
    if not keywords1 or not keywords2:
        return SimilarityScore(score=0.0, matching_keywords=[], total_keywords=0)
    
    set1 = set(k.lower() for k in keywords1)
    set2 = set(k.lower() for k in keywords2)
    
    matching = set1.intersection(set2)
    union = set1.union(set2)
    
    if not union:
        score = 0.0
    else:
        # Jaccard similarity
        score = len(matching) / len(union)
    
    return SimilarityScore(
        score=score,
        matching_keywords=sorted(list(matching)),
        total_keywords=len(union)
    )


def highlight_keywords(text: str, keywords: List[str], marker: str = "**") -> str:
    """
    Highlight keywords in text using markers.
    
    Args:
        text: Original text
        keywords: Keywords to highlight
        marker: Marker to use (default: ** for markdown bold)
        
    Returns:
        Text with highlighted keywords
    """
    if not keywords:
        return text
    
    result = text
    for keyword in sorted(keywords, key=len, reverse=True):  # Longest first
        # Case-insensitive replacement
        pattern = re.compile(re.escape(keyword), re.IGNORECASE)
        result = pattern.sub(f"{marker}\\g<0>{marker}", result)
    
    return result
