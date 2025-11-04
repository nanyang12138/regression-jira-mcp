"""
ML Model Training Module

Implements RandomForest classifier for JIRA matching improvement.
Uses 13-dimensional feature vector for prediction.
"""

from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
import pickle
import numpy as np
from pathlib import Path
from typing import List, Dict, Optional
import logging
import re

logger = logging.getLogger(__name__)


class JiraMatcherModel:
    """JIRA matching ML model using RandomForest"""
    
    def __init__(self, model_dir: str = 'ml/models'):
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        
        self.classifier = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            random_state=42,
            n_jobs=-1
        )
        
        self.vectorizer = TfidfVectorizer(
            max_features=500,
            ngram_range=(1, 2),
            min_df=2
        )
        
        self.is_trained = False
        self.training_date = None
        self.accuracy = None
        self.feature_importance = None
        
        # Try to load existing model
        self._load_model()
    
    def extract_features(
        self,
        error_signature: str,
        jira_summary: str,
        jira_description: str = ''
    ) -> np.ndarray:
        """
        Extract 13-dimensional feature vector
        
        Features:
        1. TF-IDF similarity
        2. Keyword overlap
        3-10. Error type matching (8 types)
        11-12. Text length
        13. Special patterns
        """
        features = []
        
        error_text = error_signature.lower()
        jira_text = f"{jira_summary} {jira_description}".lower()
        
        # 1. TF-IDF similarity
        try:
            if error_text and jira_text:
                tfidf_matrix = self.vectorizer.fit_transform([error_text, jira_text])
                similarity = (tfidf_matrix[0] * tfidf_matrix[1].T).toarray()[0][0]
                features.append(similarity)
            else:
                features.append(0.0)
        except:
            features.append(0.0)
        
        # 2. Keyword overlap
        error_words = set(error_text.split())
        jira_words = set(jira_text.split())
        
        if error_words:
            overlap = len(error_words & jira_words) / len(error_words)
            features.append(overlap)
        else:
            features.append(0.0)
        
        # 3-10. Error type features
        error_types = {
            'memory': ['memory', 'malloc', 'alloc', 'heap', 'leak', 'oom'],
            'crash': ['crash', 'segfault', 'sigsegv', 'abort', 'coredump'],
            'timeout': ['timeout', 'hang', 'freeze', 'stuck', 'deadlock'],
            'assertion': ['assert', 'assertion', 'invariant'],
            'null_pointer': ['null', 'nullptr', 'nil', 'undefined'],
            'io_error': ['io', 'read', 'write', 'file', 'disk'],
            'network': ['network', 'socket', 'connection'],
            'gpu': ['gpu', 'cuda', 'opencl', 'graphics', 'render']
        }
        
        for error_type, keywords in error_types.items():
            has_in_error = any(kw in error_text for kw in keywords)
            has_in_jira = any(kw in jira_text for kw in keywords)
            
            if has_in_error and has_in_jira:
                features.append(1.0)
            elif has_in_error or has_in_jira:
                features.append(0.5)
            else:
                features.append(0.0)
        
        # 11-12. Text length features
        features.append(min(len(error_text) / 100, 1.0))
        features.append(min(len(jira_text) / 500, 1.0))
        
        # 13. Special patterns
        has_error_code = bool(re.search(r'0x[0-9a-f]+|error\s+\d+', error_text))
        features.append(1.0 if has_error_code else 0.0)
        
        return np.array(features).reshape(1, -1)
    
    def train(
        self,
        training_data: List[Dict],
        test_size: float = 0.2
    ) -> Dict:
        """
        Train the model
        
        Args:
            training_data: List of feedback data
            test_size: Test set ratio for validation
            
        Returns:
            Training report
        """
        if len(training_data) < 20:
            return {
                'status': 'error',
                'message': f'Insufficient training data (need ≥20, got {len(training_data)})'
            }
        
        # Prepare features and labels
        X = []
        y = []
        
        for item in training_data:
            features = self.extract_features(
                item.get('error_signature', ''),
                item.get('jira_summary', ''),
                item.get('jira_description', '')
            )
            X.append(features[0])
            y.append(1 if item.get('is_relevant', False) else 0)
        
        X = np.array(X)
        y = np.array(y)
        
        # Cross-validation
        cv_scores = cross_val_score(self.classifier, X, y, cv=min(5, len(X)))
        self.accuracy = cv_scores.mean()
        
        # Train final model
        self.classifier.fit(X, y)
        
        # Feature importance
        self.feature_importance = self.classifier.feature_importances_
        
        self.is_trained = True
        self.training_date = datetime.now().isoformat()
        
        # Save model
        self._save_model()
        
        return {
            'status': 'success',
            'training_samples': len(training_data),
            'positive_samples': int(sum(y)),
            'negative_samples': int(len(y) - sum(y)),
            'accuracy': f'{self.accuracy:.2%}',
            'cv_scores': [f'{s:.2%}' for s in cv_scores],
            'feature_importance': self._format_feature_importance()
        }
    
    def predict_relevance(
        self,
        error_signature: str,
        jira_summary: str,
        jira_description: str = ''
    ) -> Optional[float]:
        """
        Predict JIRA relevance score
        
        Returns:
            0.0-1.0 relevance score, or None if model not trained
        """
        if not self.is_trained:
            return None
        
        features = self.extract_features(
            error_signature,
            jira_summary,
            jira_description
        )
        
        # Predict probability of being relevant
        proba = self.classifier.predict_proba(features)[0][1]
        
        return float(proba)
    
    def _save_model(self):
        """Save model to disk"""
        model_file = self.model_dir / 'jira_matcher.pkl'
        
        data = {
            'classifier': self.classifier,
            'vectorizer': self.vectorizer,
            'is_trained': self.is_trained,
            'training_date': self.training_date,
            'accuracy': self.accuracy,
            'feature_importance': self.feature_importance
        }
        
        with open(model_file, 'wb') as f:
            pickle.dump(data, f)
        
        logger.info(f"Model saved to {model_file}")
    
    def _load_model(self):
        """Load model from disk"""
        model_file = self.model_dir / 'jira_matcher.pkl'
        
        if not model_file.exists():
            logger.debug("No existing model found")
            return
        
        try:
            with open(model_file, 'rb') as f:
                data = pickle.load(f)
            
            self.classifier = data['classifier']
            self.vectorizer = data['vectorizer']
            self.is_trained = data['is_trained']
            self.training_date = data['training_date']
            self.accuracy = data.get('accuracy')
            self.feature_importance = data.get('feature_importance')
            
            logger.info(f"Model loaded (accuracy: {self.accuracy:.2%}, trained: {self.training_date})")
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
    
    def _format_feature_importance(self) -> Dict:
        """Format feature importance for display"""
        if self.feature_importance is None:
            return {}
        
        feature_names = [
            'tfidf_similarity',
            'keyword_overlap',
            'memory_match', 'crash_match', 'timeout_match', 'assertion_match',
            'null_match', 'io_match', 'network_match', 'gpu_match',
            'error_length', 'jira_length',
            'has_error_code'
        ]
        
        return dict(zip(feature_names, [float(x) for x in self.feature_importance]))
    
    def get_info(self) -> Dict:
        """Get model information"""
        return {
            'is_trained': self.is_trained,
            'training_date': self.training_date,
            'accuracy': f'{self.accuracy:.2%}' if self.accuracy else 'N/A',
            'model_type': 'RandomForestClassifier',
            'n_estimators': self.classifier.n_estimators,
            'feature_count': 13,
            'feature_importance': self._format_feature_importance() if self.is_trained else {}
        }

