"""Unified ML pipeline orchestrator."""

import os
from typing import Dict, Optional, Callable
from .data import load_data, extract_features, binarize_labels
from .classifier import TopicClassifier
from .regressor import QualityRegressor
from .clustering import HypotheticalClusterer
import structlog

logger = structlog.get_logger(__name__)


class MLPipeline:
    """Coordinates classifier, regressor, and clusterer."""

    def __init__(self, models_dir: str = "models"):
        self.models_dir = models_dir
        self.classifier = TopicClassifier()
        self.regressor = QualityRegressor()
        self.clusterer = HypotheticalClusterer()
        self._vectorizer = None
        self._binarizer = None
        self._metrics: Dict = {}
        os.makedirs(models_dir, exist_ok=True)

    def train_all(
        self,
        data_path: str,
        progress_callback: Optional[Callable] = None,
        n_clusters: int = 5,
        max_features: int = 5000,
    ):
        """Train all models from labelled CSV."""

        def _cb(pct, msg):
            if progress_callback:
                progress_callback(pct, msg)

        _cb(0.05, "Loading data")
        data = load_data(data_path)
        train_df, test_df = data["train"], data["test"]
        _cb(0.15, "Extracting features (train)")
        X_train, self._vectorizer = extract_features(
            train_df["text"], max_features=max_features
        )
        X_test, _ = extract_features(test_df["text"], vectorizer=self._vectorizer)
        # classifier
        _cb(0.25, "Training classifier")
        y_train_cls, self._binarizer = binarize_labels(train_df["topic_list"])
        y_test_cls, _ = binarize_labels(
            test_df["topic_list"], binarizer=self._binarizer
        )
        self.classifier.train(X_train, y_train_cls)
        cls_metrics = self.classifier.evaluate(
            X_test, y_test_cls, label_names=list(self._binarizer.classes_)
        )
        # regressor
        _cb(0.50, "Training regressor")
        self.regressor.train(X_train, train_df["quality_score"].values)
        reg_metrics = self.regressor.evaluate(X_test, test_df["quality_score"].values)
        # clusterer
        _cb(0.75, "Training clusterer")
        X_full, _ = extract_features(data["full"]["text"], vectorizer=self._vectorizer)
        self.clusterer.fit(X_full, n_clusters=n_clusters)
        _cb(0.90, "Saving models")
        self._save_all()
        self._metrics = {
            "classifier": cls_metrics,
            "regressor": reg_metrics,
            "clusterer": self.clusterer.get_cluster_summary(),
        }
        _cb(1.0, "Training complete")
        logger.info("ML pipeline training complete")
        return self._metrics

    def train_single(
        self,
        model_type: str,
        data_path: str,
        progress_callback: Optional[Callable] = None,
        **kwargs,
    ):
        """Train a single model type: classifier, regressor, or clusterer."""
        data = load_data(data_path)
        train_df = data["train"]
        X_train, self._vectorizer = extract_features(
            train_df["text"], max_features=kwargs.get("max_features", 5000)
        )
        if model_type == "classifier":
            y_train, self._binarizer = binarize_labels(train_df["topic_list"])
            self.classifier.train(X_train, y_train, progress_callback)
            self.classifier.save_model(
                os.path.join(self.models_dir, "classifier.joblib")
            )
        elif model_type == "regressor":
            self.regressor.train(
                X_train, train_df["quality_score"].values, progress_callback
            )
            self.regressor.save_model(os.path.join(self.models_dir, "regressor.joblib"))
        elif model_type == "clusterer":
            X_full, _ = extract_features(
                data["full"]["text"], vectorizer=self._vectorizer
            )
            self.clusterer.fit(
                X_full,
                n_clusters=kwargs.get("n_clusters", 5),
                progress_callback=progress_callback,
            )
            self.clusterer.save_model(os.path.join(self.models_dir, "clusterer.joblib"))
        else:
            raise ValueError(f"Unknown model_type: {model_type}")

    def predict(self, text: str) -> Dict:
        """Predict topics, quality, and cluster for a text."""
        if self._vectorizer is None:
            raise RuntimeError("Pipeline not trained or vectorizer not loaded")
        X = self._vectorizer.transform([text])
        result = {}
        if self.classifier.is_trained and self._binarizer is not None:
            topics = self.classifier.predict_topics(X, list(self._binarizer.classes_))
            result["topics"] = topics[0]
        if self.regressor.is_trained:
            result["quality"] = float(self.regressor.predict(X)[0])
        if self.clusterer.is_trained:
            result["cluster"] = self.clusterer.predict_cluster(X)
        return result

    def evaluate_all(self) -> Dict:
        """Return cached metrics from last training."""
        return self._metrics

    def get_status(self) -> Dict:
        """Status of trained models and metrics."""
        return {
            "classifier_trained": self.classifier.is_trained,
            "regressor_trained": self.regressor.is_trained,
            "clusterer_trained": self.clusterer.is_trained,
            "metrics": self._metrics,
        }

    def _save_all(self):
        import joblib

        self.classifier.save_model(os.path.join(self.models_dir, "classifier.joblib"))
        self.regressor.save_model(os.path.join(self.models_dir, "regressor.joblib"))
        self.clusterer.save_model(os.path.join(self.models_dir, "clusterer.joblib"))
        joblib.dump(
            self._vectorizer, os.path.join(self.models_dir, "vectorizer.joblib")
        )
        joblib.dump(self._binarizer, os.path.join(self.models_dir, "binarizer.joblib"))

    def load_all(self):
        """Load all saved models."""
        import joblib

        clf_path = os.path.join(self.models_dir, "classifier.joblib")
        reg_path = os.path.join(self.models_dir, "regressor.joblib")
        clu_path = os.path.join(self.models_dir, "clusterer.joblib")
        vec_path = os.path.join(self.models_dir, "vectorizer.joblib")
        bin_path = os.path.join(self.models_dir, "binarizer.joblib")
        if os.path.exists(clf_path):
            self.classifier.load_model(clf_path)
        if os.path.exists(reg_path):
            self.regressor.load_model(reg_path)
        if os.path.exists(clu_path):
            self.clusterer.load_model(clu_path)
        if os.path.exists(vec_path):
            self._vectorizer = joblib.load(vec_path)
        if os.path.exists(bin_path):
            self._binarizer = joblib.load(bin_path)
