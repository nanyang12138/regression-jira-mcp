"""
Error Matcher Module

Intelligent matching between test errors and JIRA issues.
Calculates similarity scores and ranks JIRA results by relevance.
"""

import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from .utils import (
    extract_keywords,
    clean_text_for_comparison,
    calculate_keyword_similarity,
    SimilarityScore
)

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

try:
    import Levenshtein
    LEVENSHTEIN_AVAILABLE = True
except ImportError:
    LEVENSHTEIN_AVAILABLE = False


@dataclass
class JiraMatch:
    """Container for a matched JIRA issue with relevance score"""
    issue_key: str
    summary: str
    description: str
    status: str
    resolution: Optional[str]
    similarity_score: float  # 0.0 to 1.0
    matching_keywords: List[str]
    relevance_reason: str
    solution_summary: Optional[str]
    link: str
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            'issue_key': self.issue_key,
            'summary': self.summary,
            'description': self.description[:500] if self.description else None,  # Truncate
            'status': self.status,
            'resolution': self.resolution,
            'similarity_score': round(self.similarity_score, 2),
            'matching_keywords': self.matching_keywords,
            'relevance_reason': self.relevance_reason,
            'solution_summary': self.solution_summary,
            'link': self.link
        }


class ErrorMatcher:
    """
    Intelligent error matcher for JIRA issues.
    
    Calculates similarity between test errors and JIRA issues using
    multiple algorithms and ranks results by relevance.
    """
    
    def __init__(self):
        """Initialize the error matcher"""
        self.use_sklearn = SKLEARN_AVAILABLE
        self.use_levenshtein = LEVENSHTEIN_AVAILABLE
    
    def match_jira_issues(
        self,
        error_signature: str,
        error_keywords: List[str],
        jira_issues: List[Dict],
        min_score: float = 0.3,
        max_results: int = 10
    ) -> List[JiraMatch]:
        """
        Match and rank JIRA issues against test error.
        
        Args:
            error_signature: Error signature from test
            error_keywords: Keywords extracted from error
            jira_issues: List of JIRA issues from search
            min_score: Minimum similarity score (0.0-1.0)
            max_results: Maximum number of results to return
            
        Returns:
            List of JiraMatch objects, sorted by relevance
        """
        if not jira_issues:
            return []
        
        matches = []
        
        for issue in jira_issues:
            # Calculate similarity score
            score, reason, matching_kw = self._calculate_similarity(
                error_signature,
                error_keywords,
                issue
            )
            
            if score >= min_score:
                # Extract solution summary
                solution = self._extract_solution(issue)
                
                # Create match object
                match = JiraMatch(
                    issue_key=issue.get('key', 'UNKNOWN'),
                    summary=issue.get('summary', ''),
                    description=issue.get('description', ''),
                    status=issue.get('status', 'Unknown'),
                    resolution=issue.get('resolution'),
                    similarity_score=score,
                    matching_keywords=matching_kw,
                    relevance_reason=reason,
                    solution_summary=solution,
                    link=issue.get('link', '')
                )
                matches.append(match)
        
        # Sort by similarity score (highest first)
        matches.sort(key=lambda x: x.similarity_score, reverse=True)
        
        return matches[:max_results]
    
    def _calculate_similarity(
        self,
        error_signature: str,
        error_keywords: List[str],
        jira_issue: Dict
    ) -> Tuple[float, str, List[str]]:
        """
        Calculate similarity between error and JIRA issue.
        
        Uses multiple methods and combines scores:
        1. Keyword matching (Jaccard similarity)
        2. Text similarity (if sklearn available)
        3. Edit distance (if Levenshtein available)
        
        Args:
            error_signature: Error signature text
            error_keywords: Keywords from error
            jira_issue: JIRA issue dictionary
            
        Returns:
            Tuple of (score, reason, matching_keywords)
        """
        jira_text = self._get_jira_text(jira_issue)
        jira_keywords = extract_keywords(jira_text, max_keywords=20)
        
        scores = []
        reasons = []
        
        # Method 1: Keyword matching (always available)
        keyword_sim = calculate_keyword_similarity(error_keywords, jira_keywords)
        scores.append(keyword_sim.score * 0.5)  # Weight: 50%
        if keyword_sim.score > 0.5:
            reasons.append(f"Keyword match: {keyword_sim}")
        
        # Method 2: Text similarity (if sklearn available)
        if self.use_sklearn:
            text_score = self._calculate_text_similarity(
                error_signature,
                jira_text
            )
            scores.append(text_score * 0.3)  # Weight: 30%
            if text_score > 0.5:
                reasons.append(f"Text similarity: {int(text_score * 100)}%")
        
        # Method 3: Edit distance (if Levenshtein available)
        if self.use_levenshtein:
            edit_score = self._calculate_edit_similarity(
                error_signature,
                jira_issue.get('summary', '')
            )
            scores.append(edit_score * 0.2)  # Weight: 20%
            if edit_score > 0.5:
                reasons.append(f"Summary match: {int(edit_score * 100)}%")
        
        # Calculate final score
        if scores:
            final_score = sum(scores)
        else:
            final_score = 0.0
        
        # Bonus for resolved issues
        if jira_issue.get('status', '').lower() in ['resolved', 'closed']:
            final_score *= 1.1  # 10% bonus
            reasons.append("Issue is resolved")
        
        # Ensure score is in range [0, 1]
        final_score = min(1.0, max(0.0, final_score))
        
        reason_text = "; ".join(reasons) if reasons else "Low similarity"
        
        return final_score, reason_text, keyword_sim.matching_keywords
    
    def _get_jira_text(self, jira_issue: Dict) -> str:
        """
        Extract all searchable text from JIRA issue.
        
        Args:
            jira_issue: JIRA issue dictionary
            
        Returns:
            Combined text for matching
        """
        parts = []
        
        # Summary (highest weight)
        if jira_issue.get('summary'):
            parts.append(jira_issue['summary'] * 2)  # Weight summary more
        
        # Description
        if jira_issue.get('description'):
            parts.append(jira_issue['description'])
        
        # Labels
        if jira_issue.get('labels'):
            parts.append(' '.join(jira_issue['labels']))
        
        # Comments (first few)
        if jira_issue.get('comments'):
            comments = jira_issue['comments'][:3]  # First 3 comments
            for comment in comments:
                if isinstance(comment, dict) and comment.get('body'):
                    parts.append(comment['body'])
        
        return ' '.join(parts)
    
    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate text similarity using TF-IDF and cosine similarity.
        
        Args:
            text1: First text
            text2: Second text
            
        Returns:
            Similarity score (0.0 to 1.0)
        """
        if not self.use_sklearn or not text1 or not text2:
            return 0.0
        
        try:
            # Clean texts
            clean1 = clean_text_for_comparison(text1)
            clean2 = clean_text_for_comparison(text2)
            
            if not clean1 or not clean2:
                return 0.0
            
            # Calculate TF-IDF vectors
            vectorizer = TfidfVectorizer(
                min_df=1,
                max_df=0.9,
                ngram_range=(1, 2),  # Unigrams and bigrams
                stop_words='english'
            )
            
            vectors = vectorizer.fit_transform([clean1, clean2])
            similarity = cosine_similarity(vectors[0:1], vectors[1:2])[0][0]
            
            return max(0.0, min(1.0, similarity))
        
        except Exception:
            return 0.0
    
    def _calculate_edit_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate similarity using Levenshtein edit distance.
        
        Args:
            text1: First text
            text2: Second text
            
        Returns:
            Similarity score (0.0 to 1.0)
        """
        if not self.use_levenshtein or not text1 or not text2:
            return 0.0
        
        try:
            # Limit text length for performance
            max_len = 200
            text1 = text1[:max_len]
            text2 = text2[:max_len]
            
            # Calculate ratio
            ratio = Levenshtein.ratio(text1.lower(), text2.lower())
            
            return max(0.0, min(1.0, ratio))
        
        except Exception:
            return 0.0
    
    def _extract_solution(self, jira_issue: Dict) -> Optional[str]:
        """
        Extract solution summary from JIRA issue.
        
        Looks for solution indicators in comments and description.
        
        Args:
            jira_issue: JIRA issue dictionary
            
        Returns:
            Solution summary or None
        """
        solution_keywords = ['solution', 'fix', 'resolved', 'patch', 'workaround', 'applied']
        
        # Check resolution field
        if jira_issue.get('resolution'):
            resolution = jira_issue['resolution']
            if resolution.lower() in ['fixed', 'done', 'resolved']:
                # Look in comments for fix details
                if jira_issue.get('comments'):
                    for comment in jira_issue['comments']:
                        if isinstance(comment, dict):
                            body = comment.get('body', '').lower()
                            for keyword in solution_keywords:
                                if keyword in body:
                                    # Extract sentence containing keyword
                                    sentences = re.split(r'[.!?]', comment.get('body', ''))
                                    for sentence in sentences:
                                        if keyword in sentence.lower():
                                            return sentence.strip()[:200]
        
        # Check description
        if jira_issue.get('description'):
            desc = jira_issue['description'].lower()
            for keyword in solution_keywords:
                if keyword in desc:
                    # Extract sentence containing keyword
                    sentences = re.split(r'[.!?]', jira_issue['description'])
                    for sentence in sentences:
                        if keyword in sentence.lower():
                            return sentence.strip()[:200]
        
        return None
    
    def compare_errors(self, error1: str, error2: str) -> float:
        """
        Compare two error signatures.
        
        Args:
            error1: First error signature
            error2: Second error signature
            
        Returns:
            Similarity score (0.0 to 1.0)
        """
        keywords1 = extract_keywords(error1)
        keywords2 = extract_keywords(error2)
        
        # Keyword similarity
        kw_sim = calculate_keyword_similarity(keywords1, keywords2)
        score = kw_sim.score * 0.6
        
        # Add text similarity if available
        if self.use_sklearn:
            text_score = self._calculate_text_similarity(error1, error2)
            score += text_score * 0.4
        
        return min(1.0, score)
    
    def suggest_jira_search_keywords(
        self,
        error_signature: str,
        error_keywords: List[str],
        max_keywords: int = 5
    ) -> List[str]:
        """
        Suggest best keywords for JIRA search based on error.
        
        Args:
            error_signature: Error signature
            error_keywords: Extracted keywords
            max_keywords: Maximum keywords to suggest
            
        Returns:
            List of suggested search keywords
        """
        # Prioritize keywords that appear in error signature
        keyword_scores = {}
        
        for kw in error_keywords:
            # Base score
            score = 1.0
            
            # Boost if appears in signature
            if kw.lower() in error_signature.lower():
                score += 2.0
            
            # Boost technical terms
            if len(kw) > 5:  # Longer words are often more specific
                score += 1.0
            
            # Boost hardware/technical terms
            technical_terms = ['memory', 'allocation', 'dma', 'cache', 'buffer',
                             'timeout', 'assertion', 'segmentation', 'fatal']
            if any(term in kw.lower() for term in technical_terms):
                score += 1.5
            
            keyword_scores[kw] = score
        
        # Sort by score and return top N
        sorted_keywords = sorted(
            keyword_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        return [kw for kw, _ in sorted_keywords[:max_keywords]]
    
    def build_jira_jql(
        self,
        keywords: List[str],
        project: Optional[str] = None,
        status_filter: Optional[str] = None
    ) -> str:
        """
        Build JQL query from keywords.
        
        Args:
            keywords: Search keywords
            project: JIRA project key
            status_filter: Status to filter by (e.g., "Resolved")
            
        Returns:
            JQL query string
        """
        parts = []
        
        # Text search with keywords
        if keywords:
            # Use OR for multiple keywords
            keyword_parts = [f'text ~ "{kw}"' for kw in keywords]
            text_query = ' OR '.join(keyword_parts)
            parts.append(f'({text_query})')
        
        # Project filter
        if project:
            parts.append(f'project = {project}')
        
        # Status filter
        if status_filter:
            if status_filter.lower() == 'resolved':
                parts.append('status IN (Resolved, Closed)')
            else:
                parts.append(f'status = {status_filter}')
        
        return ' AND '.join(parts) if parts else 'text ~ ""'
    
    def rank_by_recency(self, matches: List[JiraMatch], boost_recent: bool = True) -> List[JiraMatch]:
        """
        Re-rank matches considering recency.
        
        Args:
            matches: List of JiraMatch objects
            boost_recent: Whether to boost recent issues
            
        Returns:
            Re-ranked list
        """
        # This is a placeholder - would need issue dates to implement properly
        # For now, just return the original ranking
        return matches
    
    def filter_by_resolution(
        self,
        matches: List[JiraMatch],
        require_resolution: bool = True
    ) -> List[JiraMatch]:
        """
        Filter matches by resolution status.
        
        Args:
            matches: List of JiraMatch objects
            require_resolution: Only include resolved issues
            
        Returns:
            Filtered list
        """
        if not require_resolution:
            return matches
        
        return [
            m for m in matches
            if m.status.lower() in ['resolved', 'closed'] or m.resolution
        ]
    
    def group_by_similarity(
        self,
        matches: List[JiraMatch],
        threshold: float = 0.8
    ) -> List[List[JiraMatch]]:
        """
        Group similar JIRA matches together.
        
        Args:
            matches: List of JiraMatch objects
            threshold: Similarity threshold for grouping
            
        Returns:
            List of groups
        """
        if not matches:
            return []
        
        groups = []
        used = set()
        
        for i, match1 in enumerate(matches):
            if i in used:
                continue
            
            group = [match1]
            used.add(i)
            
            # Find similar matches
            for j, match2 in enumerate(matches[i+1:], start=i+1):
                if j in used:
                    continue
                
                # Compare summaries
                similarity = self.compare_errors(match1.summary, match2.summary)
                if similarity >= threshold:
                    group.append(match2)
                    used.add(j)
            
            groups.append(group)
        
        return groups


def calculate_simple_similarity(text1: str, text2: str) -> float:
    """
    Simple similarity calculation using keyword overlap.
    Fallback when sklearn is not available.
    
    Args:
        text1: First text
        text2: Second text
        
    Returns:
        Similarity score (0.0 to 1.0)
    """
    keywords1 = set(extract_keywords(text1, max_keywords=20))
    keywords2 = set(extract_keywords(text2, max_keywords=20))
    
    if not keywords1 or not keywords2:
        return 0.0
    
    intersection = keywords1.intersection(keywords2)
    union = keywords1.union(keywords2)
    
    if not union:
        return 0.0
    
    return len(intersection) / len(union)
