"""
错误模式自动学习器

功能:
1. 记录未匹配的错误
2. n-gram聚类分析
3. 正则表达式泛化
4. 置信度评估
5. 导出Python代码
"""

import re
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class PatternLearner:
    """错误模式自动学习器"""
    
    def __init__(self, storage_file: str = 'data/unmatched_errors.jsonl'):
        self.storage_file = Path(storage_file)
        self.storage_file.parent.mkdir(parents=True, exist_ok=True)
        self.unmatched_errors = []
    
    def record_unmatched(
        self,
        log_content: str,
        test_name: str,
        error_context: Optional[Dict] = None
    ):
        """
        记录未匹配的错误
        
        Args:
            log_content: 日志内容
            test_name: 测试名称
            error_context: 额外上下文（可选）
        """
        # 提取潜在错误行
        error_lines = self._extract_potential_errors(log_content)
        
        if not error_lines:
            logger.debug(f"No error lines found in log for {test_name}")
            return
        
        record = {
            'timestamp': datetime.now().isoformat(),
            'test_name': test_name,
            'error_lines': error_lines[:10],  # 最多保存10行
            'log_length': len(log_content),
            'context': error_context or {}
        }
        
        self.unmatched_errors.append(record)
        
        # 持久化
        try:
            with open(self.storage_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(record, ensure_ascii=False) + '\n')
            logger.debug(f"Recorded unmatched error for {test_name}")
        except Exception as e:
            logger.error(f"Failed to persist unmatched error: {e}")
    
    def _extract_potential_errors(self, log_content: str) -> List[str]:
        """提取可能是错误的行"""
        potential_errors = []
        
        # 错误指示词
        error_indicators = [
            'error', 'fail', 'exception', 'fatal', 'critical',
            'assert', 'abort', 'crash', 'segfault', 'panic',
            'timeout', 'denied', 'invalid', 'cannot', 'unable'
        ]
        
        lines = log_content.split('\n')
        
        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                continue
            
            line_lower = line_stripped.lower()
            
            # 包含错误指示词
            if any(indicator in line_lower for indicator in error_indicators):
                potential_errors.append(line_stripped)
            
            # 或者包含大写的ERROR/FATAL等
            elif re.search(r'\b(ERROR|FATAL|CRITICAL|FAIL|ABORT)\b', line_stripped):
                potential_errors.append(line_stripped)
        
        return potential_errors
    
    def analyze_patterns(
        self,
        min_frequency: int = 3,
        max_suggestions: int = 20
    ) -> Dict:
        """
        分析未匹配的错误，发现共同模式
        
        Args:
            min_frequency: 最小出现次数
            max_suggestions: 最大建议数量
            
        Returns:
            {
                'status': 'success',
                'statistics': {...},
                'suggested_patterns': [...]
            }
        """
        # 加载所有记录
        self._load_all_records()
        
        if len(self.unmatched_errors) < 10:
            return {
                'status': 'insufficient_data',
                'message': f'需要更多数据（当前: {len(self.unmatched_errors)}条记录）',
                'total_records': len(self.unmatched_errors)
            }
        
        # 收集所有错误行
        all_error_lines = []
        for record in self.unmatched_errors:
            all_error_lines.extend(record.get('error_lines', []))
        
        # 查找共同模式
        patterns = self._find_common_patterns(all_error_lines, min_frequency)
        
        # 生成建议
        suggestions = []
        for pattern_str, frequency, examples in patterns[:max_suggestions]:
            regex = self._generalize_to_regex(pattern_str)
            error_type = self._guess_error_type(pattern_str)
            confidence = self._calculate_confidence(frequency, examples)
            
            suggestions.append({
                'pattern_string': pattern_str,
                'regex': regex,
                'frequency': frequency,
                'examples': examples[:3],
                'suggested_level': error_type['level'],
                'suggested_pos': error_type['pos'],
                'confidence': confidence
            })
        
        return {
            'status': 'success',
            'statistics': {
                'total_records': len(self.unmatched_errors),
                'total_error_lines': len(all_error_lines),
                'unique_tests': len(set(r['test_name'] for r in self.unmatched_errors)),
                'date_range': self._get_date_range()
            },
            'suggested_patterns': suggestions
        }
    
    def _load_all_records(self):
        """从文件加载所有记录"""
        if not self.storage_file.exists():
            logger.debug(f"Storage file does not exist: {self.storage_file}")
            return
        
        self.unmatched_errors = []
        try:
            with open(self.storage_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        self.unmatched_errors.append(json.loads(line))
                    except json.JSONDecodeError as e:
                        logger.warning(f"Skipping invalid JSON line: {e}")
        except Exception as e:
            logger.error(f"Failed to load unmatched errors: {e}")
    
    def _find_common_patterns(
        self,
        error_lines: List[str],
        min_frequency: int
    ) -> List[Tuple[str, int, List[str]]]:
        """查找共同的3-gram模式"""
        phrase_counter = Counter()
        phrase_examples = defaultdict(list)
        
        for line in error_lines:
            # 分词
            words = re.findall(r'\S+', line)
            
            # 提取3-gram
            for i in range(len(words) - 2):
                phrase = ' '.join(words[i:i+3])
                phrase_counter[phrase] += 1
                if len(phrase_examples[phrase]) < 10:
                    phrase_examples[phrase].append(line)
        
        # 过滤低频模式并排序
        patterns = [
            (phrase, freq, phrase_examples[phrase])
            for phrase, freq in phrase_counter.items()
            if freq >= min_frequency
        ]
        
        patterns.sort(key=lambda x: x[1], reverse=True)
        return patterns
    
    def _generalize_to_regex(self, pattern_str: str) -> str:
        """将具体字符串泛化为正则表达式"""
        regex = pattern_str
        
        # 数字 -> \d+
        regex = re.sub(r'\b\d+\b', r'\\d+', regex)
        
        # 十六进制 -> 0x[0-9a-fA-F]+
        regex = re.sub(r'\b0x[0-9a-fA-F]+\b', r'0x[0-9a-fA-F]+', regex)
        
        # 文件路径 -> \S+
        regex = re.sub(r'/[\w/\.]+', r'\\S+', regex)
        
        # 长变量名 -> \w+
        regex = re.sub(r'\b[a-zA-Z_]\w{6,}\b', r'\\w+', regex)
        
        return regex
    
    def _guess_error_type(self, pattern_str: str) -> Dict:
        """根据模式内容猜测错误类型和级别"""
        pattern_lower = pattern_str.lower()
        
        error_types = {
            ('fatal', 'critical', 'panic', 'abort'): {'level': 9, 'pos': 'auto:fatal'},
            ('crash', 'segfault', 'sigsegv', 'coredump'): {'level': 8, 'pos': 'auto:crash'},
            ('memory', 'malloc', 'alloc', 'heap', 'leak'): {'level': 7, 'pos': 'auto:memory'},
            ('timeout', 'hang', 'deadlock', 'freeze'): {'level': 6, 'pos': 'auto:timeout'},
            ('assert', 'assertion', 'invariant'): {'level': 6, 'pos': 'auto:assertion'},
            ('null', 'nullptr', 'nil'): {'level': 5, 'pos': 'auto:null_pointer'},
        }
        
        for keywords, error_info in error_types.items():
            if any(kw in pattern_lower for kw in keywords):
                return error_info
        
        # 默认
        return {'level': 5, 'pos': 'auto:error'}
    
    def _calculate_confidence(self, frequency: int, examples: List[str]) -> str:
        """计算置信度"""
        if frequency >= 10:
            return 'high'
        elif frequency >= 5:
            return 'medium'
        else:
            return 'low'
    
    def _get_date_range(self) -> Dict:
        """获取数据的时间范围"""
        if not self.unmatched_errors:
            return {}
        
        timestamps = [r['timestamp'] for r in self.unmatched_errors]
        return {
            'first': min(timestamps),
            'last': max(timestamps)
        }
    
    def export_as_python_code(self, suggestions: List[Dict]) -> str:
        """导出为Python代码"""
        code_lines = [
            "# Auto-generated error patterns",
            f"# Generated at: {datetime.now().isoformat()}",
            "# Review and test before adding to error_patterns.py",
            "",
            "import re",
            "",
            "AUTO_LEARNED_PATTERNS = ["
        ]
        
        for sugg in suggestions:
            # 只导出中高置信度的模式
            if sugg['confidence'] in ['high', 'medium']:
                code_lines.append("    {")
                code_lines.append(f"        'pattern': re.compile(r'{sugg['regex']}'),")
                code_lines.append(f"        'level': {sugg['suggested_level']},")
                code_lines.append(f"        'pos': '{sugg['suggested_pos']}',")
                code_lines.append(f"        # Frequency: {sugg['frequency']}, Confidence: {sugg['confidence']}")
                
                # 添加示例作为注释
                if sugg.get('examples'):
                    example = sugg['examples'][0][:80]
                    code_lines.append(f"        # Example: {example}...")
                
                code_lines.append("    },")
        
        code_lines.append("]")
        code_lines.append("")
        code_lines.append("# Usage: Add to ERROR_PATTERNS in error_patterns.py")
        
        return '\n'.join(code_lines)
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        self._load_all_records()
        
        stats = {
            'total_records': len(self.unmatched_errors),
            'storage_file': str(self.storage_file),
        }
        
        if self.storage_file.exists():
            stats['storage_size_bytes'] = self.storage_file.stat().st_size
        else:
            stats['storage_size_bytes'] = 0
        
        if self.unmatched_errors:
            # 统计最常见的测试
            test_counter = Counter(r['test_name'] for r in self.unmatched_errors)
            stats['top_tests'] = [
                {'test_name': name, 'count': count}
                for name, count in test_counter.most_common(5)
            ]
        
        return stats

