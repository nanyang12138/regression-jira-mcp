"""
重试助手

为网络请求和临时故障提供重试机制。
"""

import time
import logging
from typing import Callable, Any, Type, Tuple
from functools import wraps

logger = logging.getLogger(__name__)


def retry_on_exception(
    max_attempts: int = 3,
    delay_seconds: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,)
):
    """
    重试装饰器
    
    Args:
        max_attempts: 最大重试次数
        delay_seconds: 初始延迟（秒）
        backoff_factor: 退避因子（每次重试延迟翻倍）
        exceptions: 要捕获的异常类型
        
    用法:
        @retry_on_exception(max_attempts=3, delay_seconds=1.0)
        def fetch_data():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            delay = delay_seconds
            
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_attempts:
                        logger.error(
                            f"Function {func.__name__} failed after {max_attempts} attempts: {e}"
                        )
                        raise
                    
                    logger.warning(
                        f"Function {func.__name__} failed (attempt {attempt}/{max_attempts}): {e}. "
                        f"Retrying in {delay}s..."
                    )
                    
                    time.sleep(delay)
                    delay *= backoff_factor
            
            # Should never reach here, but just in case
            if last_exception:
                raise last_exception
        
        return wrapper
    return decorator


def retry_on_exception_async(
    max_attempts: int = 3,
    delay_seconds: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,)
):
    """
    异步重试装饰器
    
    用法:
        @retry_on_exception_async(max_attempts=3)
        async def fetch_data_async():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            import asyncio
            
            last_exception = None
            delay = delay_seconds
            
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_attempts:
                        logger.error(
                            f"Async function {func.__name__} failed after {max_attempts} attempts: {e}"
                        )
                        raise
                    
                    logger.warning(
                        f"Async function {func.__name__} failed (attempt {attempt}/{max_attempts}): {e}. "
                        f"Retrying in {delay}s..."
                    )
                    
                    await asyncio.sleep(delay)
                    delay *= backoff_factor
            
            if last_exception:
                raise last_exception
        
        return wrapper
    return decorator


class RetryConfig:
    """重试配置"""
    
    # JIRA API重试配置
    JIRA_MAX_ATTEMPTS = 3
    JIRA_DELAY = 1.0
    JIRA_BACKOFF = 2.0
    
    # 数据库重试配置
    DB_MAX_ATTEMPTS = 2
    DB_DELAY = 0.5
    DB_BACKOFF = 2.0
    
    # 文件读取重试配置
    FILE_MAX_ATTEMPTS = 2
    FILE_DELAY = 0.1
    FILE_BACKOFF = 1.0

