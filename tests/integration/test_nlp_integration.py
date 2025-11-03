"""
集成测试：NLP与现有系统的集成

测试NLP处理器与utils和error_matcher的协同工作。
"""

import pytest
from regression_jira_mcp.nlp_utils import get_nlp_processor
from regression_jira_mcp.utils import extract_keywords_from_test_name
from regression_jira_mcp.error_matcher import ErrorMatcher


class TestNLPIntegration:
    """测试NLP集成"""
    
    def test_extract_keywords_uses_nlp(self):
        """测试关键词提取使用NLP"""
        test_name = "test_memory_allocation_failure"
        keywords = extract_keywords_from_test_name(test_name)
        
        # Should extract keywords
        assert len(keywords) > 0
        assert any('memory' in k.lower() or 'memori' in k.lower() for k in keywords)
        assert any('alloc' in k.lower() for k in keywords)
    
    def test_error_matcher_uses_nlp(self):
        """测试ErrorMatcher使用NLP进行语义匹配"""
        matcher = ErrorMatcher()
        
        # Create sample data
        error_sig = "GPU driver crashed with segmentation fault"
        error_kw = ['gpu', 'driver', 'crashed', 'segfault']
        
        jira_issues = [
            {
                'key': 'TEST-1',
                'summary': 'Fix graphics card kernel panic',
                'description': 'The display driver has a bug causing crashes',
                'status': 'Resolved',
                'resolution': 'Fixed',
                'link': 'http://test.com/TEST-1'
            }
        ]
        
        matches = matcher.match_jira_issues(
            error_signature=error_sig,
            error_keywords=error_kw,
            jira_issues=jira_issues,
            use_semantic=True
        )
        
        # Should find match with semantic understanding
        # GPU = graphics, crashed = panic, segfault = kernel fault
        assert len(matches) > 0
        assert matches[0].issue_key == 'TEST-1'
    
    def test_synonym_expansion_improves_matching(self):
        """测试同义词扩展改善匹配效果"""
        matcher = ErrorMatcher()
        
        error_sig = "Memory allocation failed"
        error_kw = ['memory', 'allocation', 'failed']
        
        jira_issues = [
            {
                'key': 'TEST-2',
                'summary': 'RAM malloc error fix',  # 同义词
                'description': 'Fixed heap allocation issue',
                'status': 'Resolved',
                'link': 'http://test.com/TEST-2'
            }
        ]
        
        # Without semantic (no synonym expansion)
        matches_no_semantic = matcher.match_jira_issues(
            error_signature=error_sig,
            error_keywords=error_kw,
            jira_issues=jira_issues,
            use_semantic=False,
            min_score=0.0
        )
        
        # With semantic (synonym expansion)
        matches_with_semantic = matcher.match_jira_issues(
            error_signature=error_sig,
            error_keywords=error_kw,
            jira_issues=jira_issues,
            use_semantic=True,
            min_score=0.0
        )
        
        # Semantic matching should have higher score
        if matches_no_semantic and matches_with_semantic:
            assert matches_with_semantic[0].similarity_score >= matches_no_semantic[0].similarity_score
    
    def test_nlp_fallback_doesnt_break_system(self):
        """测试NLP兜底不会破坏系统"""
        nlp = get_nlp_processor()
        
        # Force fallback mode
        original_nltk_available = nlp.nltk_available
        nlp.nltk_available = False
        
        try:
            # Should still work
            test_name = "test_gpu_memory_error"
            keywords = extract_keywords_from_test_name(test_name)
            
            assert len(keywords) > 0
            assert isinstance(keywords, list)
        finally:
            # Restore
            nlp.nltk_available = original_nltk_available


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

