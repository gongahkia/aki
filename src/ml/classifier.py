"""Multi-label topic classifier using sklearn OneVsRestClassifier."""

import numpy as np
from typing import Dict, List, Optional, Callable
from sklearn.multiclass import OneVsRestClassifier
from sklearn.svm import LinearSVC
from sklearn.metrics import precision_recall_fscore_support
import joblib
import structlog

logger = structlog.get_logger(__name__)


class TopicClassifier:
    """Multi-label topic classifier."""

    def __init__(self):
        self.model = None
        self.is_trained = False
        self._metrics: Dict = {}

    def train(self, X, y, progress_callback: Optional[Callable] = None):
        """Train classifier on feature matrix X and binarized labels y."""
        if progress_callback:
            progress_callback(0.1, "Training topic classifier")
        self.model = OneVsRestClassifier(LinearSVC(max_iter=5000, dual="auto"))
        self.model.fit(X, y)
        self.is_trained = True
        if progress_callback:
            progress_callback(1.0, "Classifier trained")
        logger.info("Topic classifier trained", n_samples=X.shape[0])

    def predict(self, X) -> np.ndarray:
        """Predict topic labels. Returns binarized label matrix."""
        if not self.is_trained:
            raise RuntimeError("Classifier not trained")
        return self.model.predict(X)

    def predict_topics(self, X, label_names: List[str]) -> List[List[str]]:
        """Predict and return topic name lists."""
        preds = self.predict(X)
        results = []
        for row in preds:
            topics = [label_names[i] for i, v in enumerate(row) if v == 1]
            results.append(topics)
        return results

    def evaluate(self, X, y, label_names: List[str] = None) -> Dict:
        """Evaluate returning precision, recall, f1 per topic."""
        preds = self.predict(X)
        p, r, f, s = precision_recall_fscore_support(
            y, preds, average=None, zero_division=0
        )
        overall_p, overall_r, overall_f, _ = precision_recall_fscore_support(
            y, preds, average="micro", zero_division=0
        )
        per_topic = {}
        if label_names:
            for i, name in enumerate(label_names):
                per_topic[name] = {
                    "precision": float(p[i]),
                    "recall": float(r[i]),
                    "f1": float(f[i]),
                    "support": int(s[i]),
                }
        self._metrics = {
            "per_topic": per_topic,
            "micro_precision": float(overall_p),
            "micro_recall": float(overall_r),
            "micro_f1": float(overall_f),
        }
        return self._metrics

    def save_model(self, path: str):
        joblib.dump(self.model, path)
        logger.info("Classifier saved", path=path)

    def load_model(self, path: str):
        self.model = joblib.load(path)
        self.is_trained = True
        logger.info("Classifier loaded", path=path)
