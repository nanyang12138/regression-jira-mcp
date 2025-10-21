"""
Log Analyzer Module

Python implementation of the analyzeFailure Perl function.
Analyzes test log files to extract error signatures and relevant information.
"""

import re
import os
from typing import List, Optional, Tuple
from dataclasses import dataclass
from .error_patterns import (
    COMPILED_IGNORE_PATTERNS,
    ERROR_PATTERNS,
    WARNING_PATTERNS
)
from .utils import extract_keywords, extract_keywords_from_test_name


@dataclass
class ErrorSignature:
    """
    Error signature extracted from log analysis.
    Corresponds to the Perl analyzeFailure return values.
    """
    suite: str
    test: str
    signature: str              # The error signature/message
    tool: str                   # Tool that failed
    line_number: int            # Line number in log file
    line_offset: int            # Byte offset in log file
    error_level: int            # Error severity level (1-10)
    error_line: str             # Full line containing the error
    pattern_pos: str            # Pattern that matched
    num_lines_scanned: int      # Total lines scanned
    error_keywords: List[str]   # Extracted keywords for JIRA search
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            'suite': self.suite,
            'test': self.test,
            'signature': self.signature,
            'tool': self.tool,
            'line_number': self.line_number,
            'error_level': self.error_level,
            'error_line': self.error_line,
            'pattern_pos': self.pattern_pos,
            'num_lines_scanned': self.num_lines_scanned,
            'error_keywords': self.error_keywords
        }


class LogAnalyzer:
    """
    Log file analyzer - Python implementation of Perl's analyzeFailure.
    
    This class reads test log files and identifies error patterns using
    the same rules as the original Perl implementation.
    """
    
    def __init__(self, max_lines: Optional[int] = None, ends_only: Optional[int] = None):
        """
        Initialize the log analyzer.
        
        Args:
            max_lines: Maximum number of lines to scan (None = unlimited)
            ends_only: Only scan first/last N bytes (None = scan all)
        """
        self.max_lines = max_lines
        self.ends_only = ends_only
        self.history_size = 10
        self.history: List[str] = []
        
    def analyze_failure(
        self,
        log_file_path: str,
        suite: Optional[str] = None,
        test: Optional[str] = None,
        tool: Optional[str] = None
    ) -> ErrorSignature:
        """
        Analyze a test failure log file.
        
        This is the Python equivalent of the Perl analyzeFailure subroutine.
        
        Args:
            log_file_path: Path to the log file
            suite: Test suite name (auto-detected if None)
            test: Test name (auto-detected if None)
            tool: Tool name (auto-detected if None)
            
        Returns:
            ErrorSignature object containing analysis results
        """
        # State variables (matching Perl implementation)
        failed_level = None
        failed_signature = None
        failed_tool = None
        failed_line = None
        failed_line_no = None
        failed_line_offset = None
        failed_pat_pos = None
        
        first_error_found = False
        first_error = "unknown"
        first_error_line = None
        first_error_offset = None
        treat_warnings_as_errors = False
        
        current_tool = tool
        max_lines_scanned = 0
        skipped_to_end = False
        file_size = 0
        
        # Check if file exists
        if not os.path.exists(log_file_path):
            return self._create_error_signature(
                suite or "unknown",
                test or "unknown",
                "Log file not found",
                current_tool or "unknown",
                0, 0, 1, "Log file not found",
                "error:file_not_found", 0,
                []
            )
        
        try:
            with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                # Get file size
                f.seek(0, 2)
                file_size = f.tell()
                f.seek(0)
                
                # Read and process log file
                for line_num, line in enumerate(f, 1):
                    # Update history (for advanced pattern matching)
                    self.history.insert(0, line)
                    if len(self.history) > self.history_size:
                        self.history.pop()
                    
                    max_lines_scanned += 1
                    
                    # Check line limit
                    if self.max_lines and max_lines_scanned > self.max_lines:
                        first_error = f"unknown, did not find error in first {self.max_lines} lines"
                        break
                    
                    # Handle ends_only (scan only file head and tail)
                    if self.ends_only and not skipped_to_end:
                        current_pos = f.tell()
                        if current_pos > self.ends_only:
                            skipped_to_end = True
                            new_pos = file_size - self.ends_only
                            if new_pos > current_pos:
                                f.seek(new_pos)
                                # Skip partial line
                                f.readline()
                                continue
                    
                    # Check ignore patterns
                    if self._should_ignore(line):
                        continue
                    
                    # Auto-detect suite/test from action line
                    if not suite or not test:
                        match = re.search(r'^# action: gc\(.*\)::(\w+)\/(\w+)\.(\S+)', line)
                        if match:
                            suite = match.group(1)
                            test = match.group(2)
                            if not tool:
                                current_tool = match.group(3)
                            continue
                    
                    # Extract tool name from DV output
                    tool_match = self._extract_tool_from_dv(line)
                    if tool_match:
                        current_tool = tool_match
                        continue
                    
                    # Check for "warnings as errors" flag
                    if re.search(r'cc1plus: warnings being treated as errors', line):
                        treat_warnings_as_errors = True
                        continue
                    
                    # Apply error pattern matching
                    error_match = self._match_error_patterns(
                        line,
                        current_tool or "unknown",
                        treat_warnings_as_errors
                    )
                    
                    if error_match:
                        if not first_error_found:
                            first_error_found = True
                            first_error = line.strip()
                            first_error_line = line_num
                            first_error_offset = f.tell()
                        
                        # Update if this is higher severity
                        if failed_level is None or error_match['level'] > failed_level:
                            failed_level = error_match['level']
                            failed_signature = line.strip()
                            failed_tool = current_tool
                            failed_line = line
                            failed_line_no = line_num
                            failed_line_offset = f.tell()
                            failed_pat_pos = error_match['pattern_pos']
        
        except Exception as e:
            return self._create_error_signature(
                suite or "unknown",
                test or "unknown",
                f"Error reading log file: {str(e)}",
                current_tool or "unknown",
                0, 0, 1, str(e),
                "error:read_failure", 0,
                []
            )
        
        # Set defaults if no error found
        if not first_error_found:
            if self.max_lines and max_lines_scanned > self.max_lines:
                first_error = f"unknown, did not find error in first {self.max_lines} lines"
            elif self.ends_only and skipped_to_end:
                first_error = f"unknown, did not find error in first/last {self.ends_only} bytes"
            
            failed_signature = first_error
            failed_level = 1
            failed_line = first_error
            failed_line_no = first_error_line or 0
            failed_line_offset = first_error_offset or 0
            failed_pat_pos = "unknown"
        
        # Extract keywords from error signature
        error_keywords = extract_keywords(failed_signature or first_error)
        
        # If no keywords from error, try test name
        if not error_keywords and test:
            error_keywords = extract_keywords_from_test_name(test)
        
        return self._create_error_signature(
            suite or "unknown",
            test or "unknown",
            failed_signature or first_error,
            failed_tool or current_tool or "unknown",
            failed_line_no or 0,
            failed_line_offset or 0,
            failed_level or 1,
            failed_line or first_error,
            failed_pat_pos or "unknown",
            max_lines_scanned,
            error_keywords
        )
    
    def _create_error_signature(
        self,
        suite: str,
        test: str,
        signature: str,
        tool: str,
        line_no: int,
        offset: int,
        level: int,
        line: str,
        pattern_pos: str,
        num_lines: int,
        keywords: List[str]
    ) -> ErrorSignature:
        """Helper to create ErrorSignature object"""
        return ErrorSignature(
            suite=suite,
            test=test,
            signature=signature,
            tool=tool,
            line_number=line_no,
            line_offset=offset,
            error_level=level,
            error_line=line,
            pattern_pos=pattern_pos,
            num_lines_scanned=num_lines,
            error_keywords=keywords
        )
    
    def _should_ignore(self, line: str) -> bool:
        """
        Check if line should be ignored based on ignore patterns.
        
        Args:
            line: Log line to check
            
        Returns:
            True if line should be ignored
        """
        # Special case: simctrl lines (unless they contain "failed: caught signal <num>")
        # Perl: (/simctrl/  and (not /failed:\s+caught\s+signal\s+\d+/))    and next;
        if re.search(r'simctrl', line):
            if not re.search(r'failed:\s+caught\s+signal\s+\d+', line):
                return True
        
        # Check regular ignore patterns
        for pattern in COMPILED_IGNORE_PATTERNS:
            if pattern.search(line):
                return True
        
        return False
    
    def _extract_tool_from_dv(self, line: str) -> Optional[str]:
        """
        Extract tool name from DV output lines.
        
        Args:
            line: Log line
            
        Returns:
            Tool name or None
        """
        # dv: ... running tool <tool_name>
        match = re.search(r'dv: \.\.\. running tool (\S+)', line)
        if match:
            return match.group(1)
        
        # dv: tool <tool_name> failed!
        match = re.search(r'dv: tool (\S+) failed!', line)
        if match:
            return match.group(1)
        
        return None
    
    def _match_error_patterns(
        self,
        line: str,
        tool: str,
        treat_warnings_as_errors: bool
    ) -> Optional[dict]:
        """
        Match line against error patterns.
        
        Args:
            line: Log line to check
            tool: Current tool name
            treat_warnings_as_errors: Whether to treat warnings as errors
            
        Returns:
            Dict with 'level' and 'pattern_pos' if matched, None otherwise
        """
        # Skip empty lines
        if not line.strip():
            return None
        
        # Check error patterns
        for pattern_dict in ERROR_PATTERNS:
            pattern = pattern_dict['pattern']
            if pattern.search(line):
                return {
                    'level': pattern_dict['level'],
                    'pattern_pos': pattern_dict['pos']
                }
        
        # Check warning patterns if warnings are errors
        if treat_warnings_as_errors:
            for pattern_dict in WARNING_PATTERNS:
                pattern = pattern_dict['pattern']
                if pattern.search(line):
                    return {
                        'level': pattern_dict['level'],
                        'pattern_pos': pattern_dict['pos']
                    }
        
        return None
    
    def analyze_log_content(
        self,
        log_content: str,
        suite: Optional[str] = None,
        test: Optional[str] = None,
        tool: Optional[str] = None
    ) -> ErrorSignature:
        """
        Analyze log content directly (without file path).
        
        Args:
            log_content: Log file content as string
            suite: Test suite name
            test: Test name
            tool: Tool name
            
        Returns:
            ErrorSignature object
        """
        lines = log_content.split('\n')
        
        # State variables
        failed_level = None
        failed_signature = None
        failed_tool = None
        failed_line = None
        failed_line_no = None
        failed_pat_pos = None
        
        first_error_found = False
        first_error = "unknown"
        first_error_line = None
        treat_warnings_as_errors = False
        
        current_tool = tool
        max_lines_scanned = 0
        
        for line_num, line in enumerate(lines, 1):
            # Update history
            self.history.insert(0, line)
            if len(self.history) > self.history_size:
                self.history.pop()
            
            max_lines_scanned += 1
            
            # Check line limit
            if self.max_lines and max_lines_scanned > self.max_lines:
                first_error = f"unknown, did not find error in first {self.max_lines} lines"
                break
            
            # Check ignore patterns
            if self._should_ignore(line):
                continue
            
            # Auto-detect suite/test
            if not suite or not test:
                match = re.search(r'^# action: gc\(.*\)::(\w+)\/(\w+)\.(\S+)', line)
                if match:
                    suite = match.group(1)
                    test = match.group(2)
                    if not tool:
                        current_tool = match.group(3)
                    continue
            
            # Extract tool name
            tool_match = self._extract_tool_from_dv(line)
            if tool_match:
                current_tool = tool_match
                continue
            
            # Check for warnings as errors
            if re.search(r'cc1plus: warnings being treated as errors', line):
                treat_warnings_as_errors = True
                continue
            
            # Match error patterns
            error_match = self._match_error_patterns(
                line,
                current_tool or "unknown",
                treat_warnings_as_errors
            )
            
            if error_match:
                if not first_error_found:
                    first_error_found = True
                    first_error = line.strip()
                    first_error_line = line_num
                
                # Update if higher severity
                if failed_level is None or error_match['level'] > failed_level:
                    failed_level = error_match['level']
                    failed_signature = line.strip()
                    failed_tool = current_tool
                    failed_line = line
                    failed_line_no = line_num
                    failed_pat_pos = error_match['pattern_pos']
        
        # Set defaults if no error found
        if not first_error_found:
            if self.max_lines and max_lines_scanned > self.max_lines:
                first_error = f"unknown, did not find error in first {self.max_lines} lines"
            failed_signature = first_error
            failed_level = 1
            failed_line = first_error
            failed_line_no = first_error_line or 0
            failed_pat_pos = "unknown"
        
        # Extract keywords
        error_keywords = extract_keywords(failed_signature or first_error)
        if not error_keywords and test:
            error_keywords = extract_keywords_from_test_name(test)
        
        return self._create_error_signature(
            suite or "unknown",
            test or "unknown",
            failed_signature or first_error,
            failed_tool or current_tool or "unknown",
            failed_line_no or 0,
            0,  # offset not applicable for content analysis
            failed_level or 1,
            failed_line or first_error,
            failed_pat_pos or "unknown",
            max_lines_scanned,
            error_keywords
        )
    
    def extract_all_errors(
        self,
        log_file_path: str,
        max_errors: int = 10
    ) -> List[Tuple[str, int, int]]:
        """
        Extract all error lines from log file (not just the first one).
        
        Args:
            log_file_path: Path to log file
            max_errors: Maximum number of errors to extract
            
        Returns:
            List of tuples: (error_line, line_number, error_level)
        """
        errors = []
        
        if not os.path.exists(log_file_path):
            return errors
        
        try:
            with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                treat_warnings_as_errors = False
                
                for line_num, line in enumerate(f, 1):
                    # Check ignore patterns
                    if self._should_ignore(line):
                        continue
                    
                    # Check for warnings as errors
                    if re.search(r'cc1plus: warnings being treated as errors', line):
                        treat_warnings_as_errors = True
                        continue
                    
                    # Match error patterns
                    error_match = self._match_error_patterns(
                        line,
                        "unknown",
                        treat_warnings_as_errors
                    )
                    
                    if error_match:
                        errors.append((
                            line.strip(),
                            line_num,
                            error_match['level']
                        ))
                        
                        if len(errors) >= max_errors:
                            break
        
        except Exception:
            pass
        
        return errors
    
    def get_log_tail(self, log_file_path: str, num_lines: int = 100) -> str:
        """
        Get the last N lines of a log file.
        
        Args:
            log_file_path: Path to log file
            num_lines: Number of lines to read
            
        Returns:
            Last N lines as a single string
        """
        if not os.path.exists(log_file_path):
            return "Log file not found"
        
        try:
            with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                # Read all lines and get the last N
                lines = f.readlines()
                tail_lines = lines[-num_lines:] if len(lines) > num_lines else lines
                return ''.join(tail_lines)
        except Exception as e:
            return f"Error reading log file: {str(e)}"
    
    def get_error_context(
        self,
        log_file_path: str,
        error_line_number: int,
        context_lines: int = 5
    ) -> str:
        """
        Get context around an error line.
        
        Args:
            log_file_path: Path to log file
            error_line_number: Line number of the error
            context_lines: Number of lines before and after to include
            
        Returns:
            Context as a string
        """
        if not os.path.exists(log_file_path):
            return "Log file not found"
        
        try:
            with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
                
                start = max(0, error_line_number - context_lines - 1)
                end = min(len(lines), error_line_number + context_lines)
                
                context_lines_list = []
                for i in range(start, end):
                    line_num = i + 1
                    marker = ">>> " if line_num == error_line_number else "    "
                    context_lines_list.append(f"{marker}{line_num:5d}: {lines[i].rstrip()}")
                
                return '\n'.join(context_lines_list)
        except Exception as e:
            return f"Error reading context: {str(e)}"


def quick_error_check(log_file_path: str) -> bool:
    """
    Quick check if log file contains errors.
    
    Args:
        log_file_path: Path to log file
        
    Returns:
        True if errors found, False otherwise
    """
    if not os.path.exists(log_file_path):
        return False
    
    analyzer = LogAnalyzer(max_lines=1000)
    try:
        with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                if analyzer._should_ignore(line):
                    continue
                    
                error_match = analyzer._match_error_patterns(line, "unknown", False)
                if error_match:
                    return True
    except Exception:
        pass
    
    return False
