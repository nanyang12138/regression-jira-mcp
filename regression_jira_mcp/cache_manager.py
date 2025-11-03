"""
缓存管理器

提供内存缓存功能，减少重复的数据库查询和JIRA API调用。
使用TTL（Time-To-Live）策略自动过期。
"""

from typing import Any, Optional, Callable
from datetime import datetime, timedelta
from functools import wraps
import json
import logging

logger = logging.getLogger(__name__)


class CacheManager:
    """
    简单的内存缓存管理器
    
    使用字典存储，带TTL自动过期
    """
    
    def __init__(self):
        self._cache = {}
        self.stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0
        }
    
    def get(self, key: str) -> Optional[Any]:
        """
        获取缓存值
        
        Args:
            key: 缓存键
            
        Returns:
            缓存值或None（不存在或已过期）
        """
        if key not in self._cache:
            self.stats['misses'] += 1
            return None
        
        entry = self._cache[key]
        
        # 检查是否过期
        if datetime.now() > entry['expires_at']:
            del self._cache[key]
            self.stats['evictions'] += 1
            self.stats['misses'] += 1
            return None
        
        self.stats['hits'] += 1
        return entry['value']
    
    def set(
        self, 
        key: str, 
        value: Any, 
        ttl_seconds: int = 300
    ):
        """
        设置缓存值
        
        Args:
            key: 缓存键
            value: 缓存值
            ttl_seconds: 存活时间（秒），默认5分钟
        """
        expires_at = datetime.now() + timedelta(seconds=ttl_seconds)
        
        self._cache[key] = {
            'value': value,
            'expires_at': expires_at,
            'created_at': datetime.now()
        }
    
    def delete(self, key: str):
        """删除缓存项"""
        if key in self._cache:
            del self._cache[key]
    
    def clear(self):
        """清空所有缓存"""
        count = len(self._cache)
        self._cache.clear()
        self.stats['evictions'] += count
        logger.info(f"Cleared {count} cache entries")
    
    def clear_expired(self):
        """清理过期的缓存项"""
        now = datetime.now()
        expired_keys = [
            key for key, entry in self._cache.items()
            if now > entry['expires_at']
        ]
        
        for key in expired_keys:
            del self._cache[key]
            self.stats['evictions'] += 1
        
        if expired_keys:
            logger.debug(f"Cleared {len(expired_keys)} expired cache entries")
    
    def get_stats(self) -> dict:
        """获取缓存统计"""
        total_requests = self.stats['hits'] + self.stats['misses']
        hit_rate = (self.stats['hits'] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            'total_entries': len(self._cache),
            'hits': self.stats['hits'],
            'misses': self.stats['misses'],
            'evictions': self.stats['evictions'],
            'hit_rate': f'{hit_rate:.1f}%',
            'total_requests': total_requests
        }
    
    def _make_key(self, *args, **kwargs) -> str:
        """生成缓存键"""
        # 将参数序列化为字符串
        key_parts = []
        
        for arg in args:
            key_parts.append(str(arg))
        
        for k, v in sorted(kwargs.items()):
            key_parts.append(f"{k}={v}")
        
        return ":".join(key_parts)


# 全局缓存实例
_cache_manager = None


def get_cache_manager() -> CacheManager:
    """获取缓存管理器单例"""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
    return _cache_manager


def cached(ttl_seconds: int = 300, key_prefix: str = ''):
    """
    缓存装饰器
    
    用法:
        @cached(ttl_seconds=600, key_prefix='jira')
        def get_jira_issue(issue_key):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache = get_cache_manager()
            
            # 生成缓存键
            cache_key = f"{key_prefix}:{func.__name__}:"
            cache_key += cache._make_key(*args, **kwargs)
            
            # 尝试从缓存获取
            cached_value = cache.get(cache_key)
            if cached_value is not None:
                logger.debug(f"Cache hit: {cache_key}")
                return cached_value
            
            # 缓存未命中，执行函数
            logger.debug(f"Cache miss: {cache_key}")
            result = func(*args, **kwargs)
            
            # 存入缓存
            cache.set(cache_key, result, ttl_seconds)
            
            return result
        
        return wrapper
    return decorator


def cached_async(ttl_seconds: int = 300, key_prefix: str = ''):
    """
    异步缓存装饰器
    
    用法:
        @cached_async(ttl_seconds=600, key_prefix='db')
        async def query_test(test_name):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache = get_cache_manager()
            
            # 生成缓存键
            cache_key = f"{key_prefix}:{func.__name__}:"
            cache_key += cache._make_key(*args, **kwargs)
            
            # 尝试从缓存获取
            cached_value = cache.get(cache_key)
            if cached_value is not None:
                logger.debug(f"Cache hit: {cache_key}")
                return cached_value
            
            # 缓存未命中，执行函数
            logger.debug(f"Cache miss: {cache_key}")
            result = await func(*args, **kwargs)
            
            # 存入缓存
            cache.set(cache_key, result, ttl_seconds)
            
            return result
        
        return wrapper
    return decorator

