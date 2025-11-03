"""
NLP处理器 - 带兜底机制的智能关键词提取

设计原则:
1. 优先使用高级NLP处理
2. 失败时自动回退到简单逻辑
3. 记录降级事件用于监控
"""

import re
from typing import List, Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

# 尝试导入NLTK（可选依赖）
try:
    import nltk
    from nltk.stem import PorterStemmer
    from nltk.corpus import stopwords
    NLTK_AVAILABLE = True
except ImportError:
    NLTK_AVAILABLE = False
    logger.warning("NLTK not available. Will use fallback mode.")


class NLPProcessor:
    """智能NLP处理器"""
    
    def __init__(self, enable_fallback: bool = True):
        """
        初始化NLP处理器
        
        Args:
            enable_fallback: 是否启用兜底机制（生产环境建议True）
        """
        self.enable_fallback = enable_fallback
        self.fallback_count = 0  # 统计兜底次数
        self.stats = {
            'total_calls': 0,
            'nltk_calls': 0,
            'fallback_calls': 0,
            'errors': 0
        }
        
        # 尝试初始化NLTK
        self.nltk_available = self._init_nltk() if NLTK_AVAILABLE else False
        
        if self.nltk_available:
            self.stemmer = PorterStemmer()
            standard_stops = set(stopwords.words('english'))
            # 保留技术相关词
            tech_keeps = {'error', 'fail', 'crash', 'test', 'run', 'driver'}
            self.stop_words = standard_stops - tech_keeps
        
        # 技术同义词词典
        self.synonyms = TECH_SYNONYMS
    
    def _init_nltk(self) -> bool:
        """初始化NLTK资源，失败不影响系统启动"""
        if not NLTK_AVAILABLE:
            return False
            
        required = ['stopwords', 'punkt']
        try:
            for resource in required:
                try:
                    nltk.data.find(f'corpora/{resource}')
                except LookupError:
                    logger.info(f"Downloading NLTK resource: {resource}")
                    nltk.download(resource, quiet=True)
            return True
        except Exception as e:
            logger.warning(f"NLTK initialization failed: {e}. Will use fallback mode.")
            return False
    
    def extract_keywords(
        self, 
        text: str, 
        max_keywords: int = 15
    ) -> Tuple[List[str], Dict]:
        """
        智能关键词提取（带兜底）
        
        Returns:
            Tuple[keywords, metadata]
            metadata包含: method_used, fallback_triggered等
        """
        self.stats['total_calls'] += 1
        
        metadata = {
            'method_used': 'advanced' if self.nltk_available else 'fallback',
            'fallback_triggered': False,
            'nltk_available': self.nltk_available
        }
        
        try:
            if self.nltk_available:
                # 高级NLP处理
                self.stats['nltk_calls'] += 1
                keywords = self._advanced_extraction(text, max_keywords)
            else:
                # NLTK不可用，直接使用兜底
                self.stats['fallback_calls'] += 1
                keywords = self._fallback_extraction(text, max_keywords)
                metadata['fallback_triggered'] = True
                
            return keywords, metadata
            
        except Exception as e:
            logger.error(f"NLP extraction failed: {e}")
            self.stats['errors'] += 1
            
            if self.enable_fallback:
                # 兜底机制
                self.fallback_count += 1
                self.stats['fallback_calls'] += 1
                metadata['method_used'] = 'fallback'
                metadata['fallback_triggered'] = True
                metadata['error'] = str(e)
                keywords = self._fallback_extraction(text, max_keywords)
                logger.warning(f"Used fallback extraction (count: {self.fallback_count})")
                return keywords, metadata
            else:
                raise
    
    def _advanced_extraction(self, text: str, max_keywords: int) -> List[str]:
        """高级NLP提取"""
        if not text:
            return []
        
        # 1. 提取技术术语（最高优先级）
        tech_terms = self._extract_tech_terms(text)
        
        # 2. 清理和分词
        text_clean = text.lower()
        text_clean = re.sub(r'[^a-z0-9\s_]', ' ', text_clean)
        words = text_clean.split()
        
        # 3. 词干提取 + 停用词过滤
        processed = []
        word_freq = {}
        
        for word in words:
            if word in self.stop_words or len(word) < 2:
                continue
            
            # 词干提取
            stemmed = self.stemmer.stem(word)
            processed.append(stemmed)
            word_freq[stemmed] = word_freq.get(stemmed, 0) + 1
        
        # 4. 按频率排序
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        
        # 5. 组合结果（技术术语 + 高频词）
        keywords = tech_terms + [w for w, _ in sorted_words]
        
        # 6. 去重并限制数量
        seen = set()
        result = []
        for kw in keywords:
            kw_lower = kw.lower()
            if kw_lower not in seen:
                seen.add(kw_lower)
                result.append(kw)
                if len(result) >= max_keywords:
                    break
        
        return result
    
    def _fallback_extraction(self, text: str, max_keywords: int) -> List[str]:
        """
        简单兜底提取（与原有 utils.py 兼容）
        
        这是一个保守的实现，确保即使NLTK失败也能工作
        """
        if not text:
            return []
        
        text = text.lower()
        # 保留字母、数字、下划线
        text = re.sub(r'[^a-z0-9\s_]', ' ', text)
        words = text.split()
        
        # 简单的停用词列表（硬编码，不依赖NLTK）
        simple_stops = {
            'the', 'is', 'at', 'which', 'on', 'a', 'an', 'and', 'or', 
            'but', 'in', 'with', 'to', 'for', 'of', 'as', 'by', 'from',
            'this', 'that', 'these', 'those', 'be', 'was', 'were', 'been'
        }
        
        # 过滤并去重
        keywords = []
        seen = set()
        for word in words:
            if word not in simple_stops and len(word) >= 3 and word not in seen:
                keywords.append(word)
                seen.add(word)
                if len(keywords) >= max_keywords:
                    break
        
        return keywords
    
    def _extract_tech_terms(self, text: str) -> List[str]:
        """提取技术术语"""
        terms = []
        
        patterns = {
            'abbreviation': r'\b[A-Z]{2,}\b',           # GPU, DMA, API
            'hex_address': r'\b0x[0-9a-fA-F]+\b',       # 0x1234
            'snake_case': r'\b[a-z]+_[a-z_]+\b',        # memory_allocation
            'function': r'\b[a-z_]+\(\)',                # malloc()
            'error_code': r'(?:error|errno)\s*=?\s*\d+', # error 123
        }
        
        for pattern_name, pattern in patterns.items():
            matches = re.findall(pattern, text, re.IGNORECASE)
            terms.extend(matches)
        
        # 去重，最多返回5个
        return list(dict.fromkeys(terms))[:5]
    
    def expand_with_synonyms(self, keywords: List[str]) -> List[str]:
        """使用同义词扩展关键词"""
        expanded = set(keywords)
        
        for keyword in keywords:
            keyword_lower = keyword.lower()
            for main_term, synonym_set in self.synonyms.items():
                if keyword_lower == main_term or keyword_lower in synonym_set:
                    expanded.add(main_term)
                    expanded.update(synonym_set)
        
        return list(expanded)
    
    def calculate_semantic_similarity(self, text1: str, text2: str) -> float:
        """计算语义相似度（考虑同义词）"""
        kw1, _ = self.extract_keywords(text1)
        kw2, _ = self.extract_keywords(text2)
        
        # 扩展同义词
        kw1_expanded = set(self.expand_with_synonyms(kw1))
        kw2_expanded = set(self.expand_with_synonyms(kw2))
        
        # Jaccard相似度
        intersection = len(kw1_expanded & kw2_expanded)
        union = len(kw1_expanded | kw2_expanded)
        
        return intersection / union if union > 0 else 0.0
    
    def get_stats(self) -> Dict:
        """获取NLP处理器统计信息"""
        return {
            'nltk_available': self.nltk_available,
            'fallback_enabled': self.enable_fallback,
            'fallback_count': self.fallback_count,
            'synonyms_loaded': len(self.synonyms),
            'total_calls': self.stats['total_calls'],
            'nltk_calls': self.stats['nltk_calls'],
            'fallback_calls': self.stats['fallback_calls'],
            'errors': self.stats['errors']
        }


# 技术同义词词典
TECH_SYNONYMS = {
    'memory': {'mem', 'ram', 'heap', 'allocation', 'malloc', 'alloc'},
    'crash': {'segfault', 'sigsegv', 'sigabrt', 'abort', 'coredump', 'panic', 'fault'},
    'timeout': {'hang', 'freeze', 'stuck', 'deadlock', 'unresponsive', 'blocked'},
    'null': {'nullptr', 'nil', 'none', 'undefined', 'invalid'},
    'gpu': {'graphics', 'render', 'display', 'cuda', 'opencl', 'vulkan'},
    'fail': {'failure', 'failed', 'failing', 'error', 'unsuccessful'},
    'network': {'socket', 'connection', 'tcp', 'udp', 'http', 'https'},
    'io': {'read', 'write', 'file', 'disk', 'storage'},
    'assert': {'assertion', 'invariant', 'precondition', 'postcondition'},
    'driver': {'kernel', 'module', 'firmware'},
}


# 全局单例
_nlp_processor = None


def get_nlp_processor() -> NLPProcessor:
    """获取NLP处理器单例"""
    global _nlp_processor
    if _nlp_processor is None:
        _nlp_processor = NLPProcessor(enable_fallback=True)
    return _nlp_processor

