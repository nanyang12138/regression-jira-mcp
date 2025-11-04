"""
Feedback Storage Layer - SQLite Implementation

Stores user feedback on JIRA match quality for ML model training.
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
import threading
import logging

logger = logging.getLogger(__name__)


class FeedbackStorage:
    """Feedback data storage using SQLite"""
    
    def __init__(self, db_path: str = 'data/feedback.db'):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()
    
    def _init_db(self):
        """Initialize database schema"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    test_name TEXT NOT NULL,
                    error_signature TEXT,
                    error_keywords TEXT,
                    jira_key TEXT NOT NULL,
                    jira_summary TEXT,
                    jira_description TEXT,
                    is_relevant INTEGER NOT NULL,
                    relevance_score INTEGER,
                    comments TEXT,
                    metadata TEXT
                )
            ''')
            
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_timestamp 
                ON feedback(timestamp)
            ''')
            
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_test_name 
                ON feedback(test_name)
            ''')
            
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_jira_key 
                ON feedback(jira_key)
            ''')
    
    def add_feedback(
        self,
        test_name: str,
        jira_key: str,
        is_relevant: bool,
        error_signature: str = '',
        error_keywords: List[str] = None,
        jira_summary: str = '',
        jira_description: str = '',
        relevance_score: Optional[int] = None,
        comments: str = '',
        metadata: Optional[Dict] = None
    ) -> int:
        """
        Add feedback record
        
        Returns:
            Feedback ID
        """
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('''
                    INSERT INTO feedback (
                        timestamp, test_name, error_signature, error_keywords,
                        jira_key, jira_summary, jira_description,
                        is_relevant, relevance_score, comments, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    datetime.now().isoformat(),
                    test_name,
                    error_signature,
                    json.dumps(error_keywords or []),
                    jira_key,
                    jira_summary,
                    jira_description,
                    1 if is_relevant else 0,
                    relevance_score,
                    comments,
                    json.dumps(metadata or {})
                ))
                return cursor.lastrowid
    
    def get_training_data(
        self,
        min_samples: int = 20
    ) -> Optional[List[Dict]]:
        """
        Get training data for ML model
        
        Returns:
            List of training samples or None if insufficient
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('''
                SELECT * FROM feedback
                ORDER BY timestamp DESC
            ''')
            
            rows = cursor.fetchall()
            
            if len(rows) < min_samples:
                return None
            
            data = []
            for row in rows:
                data.append({
                    'test_name': row['test_name'],
                    'error_signature': row['error_signature'],
                    'error_keywords': json.loads(row['error_keywords']),
                    'jira_key': row['jira_key'],
                    'jira_summary': row['jira_summary'],
                    'jira_description': row['jira_description'],
                    'is_relevant': bool(row['is_relevant']),
                    'timestamp': row['timestamp']
                })
            
            return data
    
    def get_stats(self) -> Dict:
        """Get feedback statistics"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT 
                    COUNT(*) as total,
                    SUM(is_relevant) as positive,
                    MIN(timestamp) as first_feedback,
                    MAX(timestamp) as last_feedback
                FROM feedback
            ''')
            
            row = cursor.fetchone()
            
            return {
                'total_feedback': row[0] if row else 0,
                'positive_feedback': row[1] if row and row[1] else 0,
                'negative_feedback': (row[0] - row[1]) if row and row[1] else row[0] if row else 0,
                'first_feedback': row[2] if row else None,
                'last_feedback': row[3] if row else None
            }
    
    def export_to_csv(self, output_path: str):
        """Export feedback to CSV"""
        import csv
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('SELECT * FROM feedback')
            
            with open(output_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([desc[0] for desc in cursor.description])
                writer.writerows(cursor.fetchall())

