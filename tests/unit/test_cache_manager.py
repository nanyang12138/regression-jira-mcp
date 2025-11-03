"""
Unit tests for cache manager

Tests caching functionality and TTL expiration.
"""

import pytest
import time
from regression_jira_mcp.cache_manager import CacheManager, get_cache_manager


class TestCacheManager:
    """Test cache manager functionality"""
    
    def test_initialization(self):
        """Test cache manager initializes correctly"""
        cache = CacheManager()
        assert cache is not None
        assert cache._cache == {}
        assert cache.stats['hits'] == 0
        assert cache.stats['misses'] == 0
    
    def test_set_and_get(self):
        """Test basic set and get operations"""
        cache = CacheManager()
        
        cache.set('key1', 'value1', ttl_seconds=60)
        value = cache.get('key1')
        
        assert value == 'value1'
        assert cache.stats['hits'] == 1
        assert cache.stats['misses'] == 0
    
    def test_cache_miss(self):
        """Test cache miss"""
        cache = CacheManager()
        
        value = cache.get('nonexistent_key')
        
        assert value is None
        assert cache.stats['hits'] == 0
        assert cache.stats['misses'] == 1
    
    def test_ttl_expiration(self):
        """Test TTL expiration"""
        cache = CacheManager()
        
        # Set with 1 second TTL
        cache.set('key1', 'value1', ttl_seconds=1)
        
        # Should be available immediately
        value = cache.get('key1')
        assert value == 'value1'
        
        # Wait for expiration
        time.sleep(1.1)
        
        # Should be expired
        value = cache.get('key1')
        assert value is None
        assert cache.stats['evictions'] == 1
    
    def test_delete(self):
        """Test cache deletion"""
        cache = CacheManager()
        
        cache.set('key1', 'value1')
        cache.delete('key1')
        
        value = cache.get('key1')
        assert value is None
    
    def test_clear(self):
        """Test cache clearing"""
        cache = CacheManager()
        
        cache.set('key1', 'value1')
        cache.set('key2', 'value2')
        cache.set('key3', 'value3')
        
        cache.clear()
        
        assert cache.get('key1') is None
        assert cache.get('key2') is None
        assert cache.get('key3') is None
        assert cache.stats['evictions'] == 3
    
    def test_clear_expired(self):
        """Test clearing only expired entries"""
        cache = CacheManager()
        
        # Short TTL
        cache.set('expire_soon', 'value1', ttl_seconds=1)
        # Long TTL
        cache.set('keep_alive', 'value2', ttl_seconds=60)
        
        # Wait for first to expire
        time.sleep(1.1)
        
        # Clear expired
        cache.clear_expired()
        
        # Short TTL should be gone
        assert cache.get('expire_soon') is None
        # Long TTL should remain
        assert cache.get('keep_alive') == 'value2'
    
    def test_stats(self):
        """Test statistics tracking"""
        cache = CacheManager()
        
        cache.set('key1', 'value1')
        cache.get('key1')  # Hit
        cache.get('key1')  # Hit
        cache.get('key2')  # Miss
        
        stats = cache.stats('stats')
        
        assert stats['hits'] == 2
        assert stats['misses'] == 1
        assert stats['total_requests'] == 3
        # Hit rate should be 66.7%
        assert '66' in stats['hit_rate'] or '67' in stats['hit_rate']
    
    def test_complex_data_types(self):
        """Test caching complex data types"""
        cache = CacheManager()
        
        # Dictionary
        cache.set('dict', {'a': 1, 'b': 2})
        assert cache.get('dict') == {'a': 1, 'b': 2}
        
        # List
        cache.set('list', [1, 2, 3])
        assert cache.get('list') == [1, 2, 3]
        
        # Nested structure
        cache.set('nested', {'data': [1, 2], 'meta': {'count': 2}})
        assert cache.get('nested')['data'] == [1, 2]
    
    def test_singleton_pattern(self):
        """Test get_cache_manager returns singleton"""
        cache1 = get_cache_manager()
        cache2 = get_cache_manager()
        
        assert cache1 is cache2
        
        # Set in one, get from another
        cache1.set('key1', 'value1')
        assert cache2.get('key1') == 'value1'


class TestCacheDecorators:
    """Test cache decorators"""
    
    def test_cached_decorator(self):
        """Test @cached decorator"""
        call_count = {'value': 0}
        cache = CacheManager()
        
        from regression_jira_mcp.cache_manager import cached
        
        @cached(ttl_seconds=60, key_prefix='test')
        def expensive_function(x):
            call_count['value'] += 1
            return x * 2
        
        # First call - cache miss
        result1 = expensive_function(5)
        assert result1 == 10
        assert call_count['value'] == 1
        
        # Second call - cache hit
        result2 = expensive_function(5)
        assert result2 == 10
        assert call_count['value'] == 1  # Not called again!
        
        # Different argument - cache miss
        result3 = expensive_function(10)
        assert result3 == 20
        assert call_count['value'] == 2


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

