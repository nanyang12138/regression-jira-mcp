"""
结构化日志配置

提供统一的日志配置和格式化。
"""

import logging
import sys
from typing import Optional


def setup_logging(
    level: str = 'INFO',
    log_file: Optional[str] = None,
    format_json: bool = False
):
    """
    配置日志系统
    
    Args:
        level: 日志级别 (DEBUG, INFO, WARNING, ERROR)
        log_file: 日志文件路径（可选）
        format_json: 是否使用JSON格式（方便机器解析）
    """
    # 日志级别
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    
    # 日志格式
    if format_json:
        # JSON格式（结构化日志）
        log_format = '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "module": "%(name)s", "message": "%(message)s"}'
    else:
        # 人类可读格式
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # 配置根logger
    handlers = []
    
    # 控制台输出
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(logging.Formatter(log_format))
    handlers.append(console_handler)
    
    # 文件输出（如果指定）
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(logging.Formatter(log_format))
        handlers.append(file_handler)
    
    # 配置根logger
    logging.basicConfig(
        level=numeric_level,
        handlers=handlers,
        force=True
    )
    
    # 降低某些第三方库的日志级别
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('jira').setLevel(logging.WARNING)


class StructuredLogger:
    """
    结构化日志记录器
    
    提供额外的上下文信息和错误追踪
    """
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.context = {}
    
    def set_context(self, **kwargs):
        """设置上下文信息"""
        self.context.update(kwargs)
    
    def clear_context(self):
        """清除上下文"""
        self.context = {}
    
    def _format_message(self, message: str, extra: dict = None) -> str:
        """格式化消息（包含上下文）"""
        parts = [message]
        
        # 添加上下文
        if self.context:
            context_str = ', '.join(f"{k}={v}" for k, v in self.context.items())
            parts.append(f"[{context_str}]")
        
        # 添加额外信息
        if extra:
            extra_str = ', '.join(f"{k}={v}" for k, v in extra.items())
            parts.append(f"({extra_str})")
        
        return ' '.join(parts)
    
    def debug(self, message: str, **extra):
        """Debug日志"""
        self.logger.debug(self._format_message(message, extra))
    
    def info(self, message: str, **extra):
        """Info日志"""
        self.logger.info(self._format_message(message, extra))
    
    def warning(self, message: str, **extra):
        """Warning日志"""
        self.logger.warning(self._format_message(message, extra))
    
    def error(self, message: str, exc_info: bool = False, **extra):
        """Error日志"""
        self.logger.error(self._format_message(message, extra), exc_info=exc_info)
    
    def critical(self, message: str, exc_info: bool = False, **extra):
        """Critical日志"""
        self.logger.critical(self._format_message(message, extra), exc_info=exc_info)


def get_logger(name: str, structured: bool = False):
    """
    获取logger实例
    
    Args:
        name: Logger名称（通常是模块名）
        structured: 是否使用结构化logger
        
    Returns:
        Logger实例
    """
    if structured:
        return StructuredLogger(name)
    else:
        return logging.getLogger(name)

