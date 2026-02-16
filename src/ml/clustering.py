"""Hypothetical clustering using sklearn KMeans and DBSCAN."""

from typing import Callable, Dict, Optional

import joblib
import numpy as np
import structlog
from sklearn.cluster import DBSCAN, KMeans

logger = structlog.get_logger(__name__)


class HypotheticalClusterer:
    """Clustering on TF-IDF vectors of hypotheticals."""

    def __init__(self, method: str = "kmeans"):
        self.method = method
        self.model = None
        self.is_trained = False
        self._cluster_stats: Dict = {}

    def fit(self, X, n_clusters: int = 5, progress_callback: Optional[Callable] = None):
        """Fit clustering model on feature matrix X."""
        if progress_callback:
            progress_callback(0.1, f"Fitting {self.method} clusterer")
        if self.method == "kmeans":
            self.model = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        else:
            self.model = DBSCAN(eps=0.5, min_samples=2)
        labels = self.model.fit_predict(X.toarray() if hasattr(X, "toarray") else X)
        self.is_trained = True
        self._compute_stats(labels)
        if progress_callback:
            progress_callback(1.0, "Clustering complete")
        logger.info(
            "Clusterer fitted", method=self.method, n_clusters=len(set(labels) - {-1})
        )
        return labels

    def predict_cluster(self, X) -> int:
        """Predict cluster for a single sample."""
        if not self.is_trained:
            raise RuntimeError("Clusterer not trained")
        if self.method == "kmeans":
            arr = X.toarray() if hasattr(X, "toarray") else X
            return int(self.model.predict(arr)[0])
        return -1  # DBSCAN has no predict

    def get_cluster_summary(self) -> Dict:
        """Return cluster statistics."""
        return self._cluster_stats

    def visualize_clusters(self) -> str:
        """ASCII table of cluster stats."""
        lines = [f"{'Cluster':<10} {'Size':<10} {'Pct':<10}"]
        lines.append("-" * 30)
        total = sum(s["size"] for s in self._cluster_stats.values())
        for cid, stats in sorted(self._cluster_stats.items()):
            pct = (stats["size"] / total * 100) if total > 0 else 0
            lines.append(f"{cid:<10} {stats['size']:<10} {pct:<10.1f}%")
        return "\n".join(lines)

    def _compute_stats(self, labels):
        unique, counts = np.unique(labels, return_counts=True)
        self._cluster_stats = {int(u): {"size": int(c)} for u, c in zip(unique, counts)}

    def save_model(self, path: str):
        joblib.dump(
            {"model": self.model, "method": self.method, "stats": self._cluster_stats},
            path,
        )
        logger.info("Clusterer saved", path=path)

    def load_model(self, path: str):
        data = joblib.load(path)
        self.model = data["model"]
        self.method = data["method"]
        self._cluster_stats = data["stats"]
        self.is_trained = True
        logger.info("Clusterer loaded", path=path)
