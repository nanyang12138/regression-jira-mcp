"""
Unit tests for pattern learner

Tests the pattern learning functionality.
"""

import pytest
import json
import tempfile
from pathlib import Path
from regression_jira_mcp.pattern_learner import PatternLearner


class TestPatternLearner:
    """Test pattern learner functionality"""
    
    def test_initialization(self):
        """Test pattern learner initializes correctly"""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = Path(tmpdir) / 'test_unmatched.jsonl'
            learner = PatternLearner(storage_file=str(storage))
            
            assert learner is not None
            assert learner.storage_file == storage
            assert learner.unmatched_errors == []
    
    def test_record_unmatched(self):
        """Test recording unmatched errors"""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = Path(tmpdir) / 'test_unmatched.jsonl'
            learner = PatternLearner(storage_file=str(storage))
            
            log_content = """
[INFO] Starting test
[ERROR] CUDA error 700 at driver.cu:234
[FATAL] Fatal error occurred
"""
            
            learner.record_unmatched(log_content, "test_cuda_1")
            
            # Should have recorded
            assert len(learner.unmatched_errors) == 1
            assert learner.unmatched_errors[0]['test_name'] == "test_cuda_1"
            assert len(learner.unmatched_errors[0]['error_lines']) > 0
            
            # File should exist
            assert storage.exists()
    
    def test_extract_potential_errors(self):
        """Test error line extraction"""
        learner = PatternLearner()
        
        log_content = """
[INFO] Starting test
[ERROR] Memory allocation failed
Some normal output
[FATAL] Critical error
More normal output
"""
        
        errors = learner._extract_potential_errors(log_content)
        
        # Should extract lines with ERROR and FATAL
        assert len(errors) >= 2
        assert any('ERROR' in e or 'error' in e.lower() for e in errors)
        assert any('FATAL' in e or 'fatal' in e.lower() for e in errors)
    
    def test_analyze_patterns_insufficient_data(self):
        """Test analysis with insufficient data"""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = Path(tmpdir) / 'test_unmatched.jsonl'
            learner = PatternLearner(storage_file=str(storage))
            
            # Record only a few errors
            learner.record_unmatched("error 1", "test1")
            learner.record_unmatched("error 2", "test2")
            
            result = learner.analyze_patterns()
            
            assert result['status'] == 'insufficient_data'
    
    def test_analyze_patterns_with_data(self):
        """Test pattern analysis with sufficient data"""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = Path(tmpdir) / 'test_unmatched.jsonl'
            learner = PatternLearner(storage_file=str(storage))
            
            # Record multiple similar errors
            for i in range(12):
                learner.record_unmatched(
                    f"CUDA error {700+i} at driver.cu:{200+i}\nFatal error",
                    f"test_cuda_{i}"
                )
            
            result = learner.analyze_patterns(min_frequency=3)
            
            assert result['status'] == 'success'
            assert 'statistics' in result
            assert 'suggested_patterns' in result
            assert result['statistics']['total_records'] >= 12
    
    def test_regex_generalization(self):
        """Test regex generalization"""
        learner = PatternLearner()
        
        # Test number generalization
        regex = learner._generalize_to_regex("error 123 occurred")
        assert r'\d+' in regex
        
        # Test hex generalization
        regex = learner._generalize_to_regex("at address 0x1234abcd")
        assert '0x[0-9a-fA-F]+' in regex
        
        # Test path generalization
        regex = learner._generalize_to_regex("failed at /usr/lib/driver.so")
        assert r'\S+' in regex
    
    def test_error_type_guessing(self):
        """Test error type classification"""
        learner = PatternLearner()
        
        # Fatal error
        error_type = learner._guess_error_type("FATAL system crash")
        assert error_type['level'] == 9
        assert 'fatal' in error_type['pos']
        
        # Memory error
        error_type = learner._guess_error_type("memory allocation failed")
        assert error_type['level'] == 7
        assert 'memory' in error_type['pos']
        
        # Generic error
        error_type = learner._guess_error_type("something went wrong")
        assert error_type['level'] == 5
    
    def test_confidence_calculation(self):
        """Test confidence level calculation"""
        learner = PatternLearner()
        
        # High confidence
        confidence = learner._calculate_confidence(15, [])
        assert confidence == 'high'
        
        # Medium confidence
        confidence = learner._calculate_confidence(7, [])
        assert confidence == 'medium'
        
        # Low confidence
        confidence = learner._calculate_confidence(3, [])
        assert confidence == 'low'
    
    def test_export_python_code(self):
        """Test Python code export"""
        learner = PatternLearner()
        
        suggestions = [
            {
                'regex': r'CUDA error \d+',
                'frequency': 15,
                'confidence': 'high',
                'suggested_level': 7,
                'suggested_pos': 'auto:cuda_error',
                'examples': ['CUDA error 700 at driver.cu:234']
            },
            {
                'regex': r'timeout \w+',
                'frequency': 3,
                'confidence': 'low',
                'suggested_level': 6,
                'suggested_pos': 'auto:timeout',
                'examples': []
            }
        ]
        
        code = learner.export_as_python_code(suggestions)
        
        # Should generate valid Python code
        assert 'AUTO_LEARNED_PATTERNS' in code
        assert 're.compile' in code
        assert 'CUDA error' in code
        # Low confidence should be excluded
        assert 'timeout' not in code or confidence == 'low'
    
    def test_get_stats(self):
        """Test statistics retrieval"""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = Path(tmpdir) / 'test_unmatched.jsonl'
            learner = PatternLearner(storage_file=str(storage))
            
            # Record some errors
            for i in range(5):
                learner.record_unmatched(
                    f"error {i}",
                    f"test_{i}"
                )
            
            stats = learner.get_stats()
            
            assert stats['total_records'] == 5
            assert 'storage_file' in stats
            assert 'top_tests' in stats


class TestPatternLearnerPersistence:
    """Test data persistence"""
    
    def test_persistence_across_instances(self):
        """Test that data persists across instances"""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = Path(tmpdir) / 'test_unmatched.jsonl'
            
            # Instance 1: Record some errors
            learner1 = PatternLearner(storage_file=str(storage))
            learner1.record_unmatched("error 1", "test1")
            learner1.record_unmatched("error 2", "test2")
            
            # Instance 2: Should load existing data
            learner2 = PatternLearner(storage_file=str(storage))
            learner2._load_all_records()
            
            assert len(learner2.unmatched_errors) == 2
    
    def test_jsonl_format(self):
        """Test JSONL format correctness"""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = Path(tmpdir) / 'test_unmatched.jsonl'
            learner = PatternLearner(storage_file=str(storage))
            
            learner.record_unmatched("test error", "test_name")
            
            # Read file and validate JSON
            with open(storage) as f:
                line = f.readline()
                data = json.loads(line)
                
                assert 'timestamp' in data
                assert 'test_name' in data
                assert data['test_name'] == 'test_name'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

