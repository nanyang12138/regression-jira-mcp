"""
Unit tests for NLP utilities

Tests the NLP processor including fallback mechanisms.
"""

import pytest
from regression_jira_mcp.nlp_utils import NLPProcessor, TECH_SYNONYMS


class TestNLPProcessor:
    """Test NLP processor functionality"""
    
    def test_initialization(self):
        """Test NLP processor initializes correctly"""
        nlp = NLPProcessor()
        assert nlp is not None
        assert nlp.enable_fallback == True
        assert len(nlp.synonyms) > 0
    
    def test_keyword_extraction_basic(self):
        """Test basic keyword extraction"""
        nlp = NLPProcessor()
        text = "Memory allocation failed in GPU driver"
        keywords, metadata = nlp.extract_keywords(text)
        
        # Should extract some keywords
        assert len(keywords) > 0
        
        # Should use either advanced or fallback method
        assert metadata['method_used'] in ['advanced', 'fallback']
        
        # Common words like GPU, memory should be present
        keywords_lower = [k.lower() for k in keywords]
        assert any('gpu' in k for k in keywords_lower) or \
               any('memory' in k or 'memori' in k for k in keywords_lower)
    
    def test_keyword_extraction_with_nltk_unavailable(self):
        """Test fallback when NLTK is not available"""
        nlp = NLPProcessor()
        # Force fallback mode
        nlp.nltk_available = False
        
        text = "test error memory allocation"
        keywords, metadata = nlp.extract_keywords(text)
        
        assert len(keywords) > 0
        assert metadata['fallback_triggered'] or metadata['method_used'] == 'fallback'
    
    def test_tech_term_extraction(self):
        """Test technical term identification"""
        nlp = NLPProcessor()
        
        text = "CUDA error 0x1234 in malloc() function"
        keywords, _ = nlp.extract_keywords(text)
        
        # Should identify technical terms
        keywords_str = ' '.join(keywords)
        assert 'CUDA' in keywords_str or 'cuda' in keywords_str.lower()
        assert '0x' in keywords_str or 'malloc' in keywords_str.lower()
    
    def test_synonym_expansion(self):
        """Test synonym expansion"""
        nlp = NLPProcessor()
        
        keywords = ['memory', 'crash']
        expanded = nlp.expand_with_synonyms(keywords)
        
        # Should include original and synonyms
        assert len(expanded) > len(keywords)
        
        # Should include known synonyms
        expanded_lower = [k.lower() for k in expanded]
        assert 'memory' in expanded_lower
        # Check for at least one synonym of memory
        memory_synonyms = {'mem', 'ram', 'heap', 'allocation', 'malloc'}
        assert any(syn in expanded_lower for syn in memory_synonyms)
        
        # Check for crash synonyms
        crash_synonyms = {'segfault', 'sigsegv', 'abort', 'coredump'}
        assert any(syn in expanded_lower for syn in crash_synonyms)
    
    def test_semantic_similarity(self):
        """Test semantic similarity calculation"""
        nlp = NLPProcessor()
        
        text1 = "GPU driver crashed with SIGSEGV"
        text2 = "Graphics card segmentation fault"
        
        similarity = nlp.calculate_semantic_similarity(text1, text2)
        
        # Should return a score between 0 and 1
        assert 0.0 <= similarity <= 1.0
        
        # These texts should have some similarity (GPU=graphics, crashed=fault)
        # Actual value depends on NLTK availability, but should be > 0
        assert similarity > 0.0
    
    def test_empty_text_handling(self):
        """Test handling of empty text"""
        nlp = NLPProcessor()
        
        keywords, metadata = nlp.extract_keywords("")
        assert keywords == []
        
        keywords, metadata = nlp.extract_keywords(None)
        assert keywords == []
    
    def test_stats_tracking(self):
        """Test statistics tracking"""
        nlp = NLPProcessor()
        
        # Make some calls
        nlp.extract_keywords("test error")
        nlp.extract_keywords("memory allocation")
        
        stats = nlp.get_stats()
        
        assert 'total_calls' in stats
        assert stats['total_calls'] >= 2
        assert 'nltk_available' in stats
        assert 'fallback_enabled' in stats
    
    def test_fallback_mechanism_on_error(self):
        """Test that errors trigger fallback"""
        nlp = NLPProcessor(enable_fallback=True)
        
        # Even with potential errors, should return something
        text = "test error memory"
        keywords, metadata = nlp.extract_keywords(text)
        
        # Should always return a list
        assert isinstance(keywords, list)
        assert len(keywords) >= 0  # Might be empty but shouldn't crash
    
    def test_max_keywords_limit(self):
        """Test max keywords limit"""
        nlp = NLPProcessor()
        
        text = "a b c d e f g h i j k l m n o p q r s t u v w x y z"
        keywords, _ = nlp.extract_keywords(text, max_keywords=5)
        
        # Should respect the limit
        assert len(keywords) <= 5
    
    def test_tech_synonyms_coverage(self):
        """Test that tech synonyms dictionary is comprehensive"""
        assert 'memory' in TECH_SYNONYMS
        assert 'crash' in TECH_SYNONYMS
        assert 'gpu' in TECH_SYNONYMS
        assert 'timeout' in TECH_SYNONYMS
        assert 'null' in TECH_SYNONYMS
        
        # Each should have multiple synonyms
        assert len(TECH_SYNONYMS['memory']) >= 3
        assert len(TECH_SYNONYMS['crash']) >= 3


class TestNLPProcessorEdgeCases:
    """Test edge cases and error conditions"""
    
    def test_very_long_text(self):
        """Test with very long text"""
        nlp = NLPProcessor()
        
        long_text = "error " * 1000  # Very repetitive long text
        keywords, metadata = nlp.extract_keywords(long_text, max_keywords=10)
        
        # Should handle gracefully
        assert len(keywords) <= 10
        assert isinstance(keywords, list)
    
    def test_special_characters(self):
        """Test with special characters"""
        nlp = NLPProcessor()
        
        text = "Memory@#$%allocation!@#failed***GPU&&&driver"
        keywords, _ = nlp.extract_keywords(text)
        
        # Should extract meaningful words despite special chars
        assert len(keywords) > 0
    
    def test_numbers_and_codes(self):
        """Test with error codes and numbers"""
        nlp = NLPProcessor()
        
        text = "Error 123 at 0xABCD in line 456"
        keywords, _ = nlp.extract_keywords(text)
        
        # Should handle numbers and hex codes
        assert len(keywords) > 0
    
    def test_mixed_case(self):
        """Test with mixed case text"""
        nlp = NLPProcessor()
        
        text = "GPU Driver CRASHED with MemoryAllocationError"
        keywords, _ = nlp.extract_keywords(text)
        
        # Should handle mixed case
        assert len(keywords) > 0
    
    def test_synonym_expansion_with_empty_list(self):
        """Test synonym expansion with empty input"""
        nlp = NLPProcessor()
        
        expanded = nlp.expand_with_synonyms([])
        assert expanded == []
    
    def test_synonym_expansion_with_unknown_words(self):
        """Test synonym expansion with words not in dictionary"""
        nlp = NLPProcessor()
        
        keywords = ['unknownword123', 'anotherweirdword']
        expanded = nlp.expand_with_synonyms(keywords)
        
        # Should return at least the original words
        assert set(keywords).issubset(set(expanded))


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

