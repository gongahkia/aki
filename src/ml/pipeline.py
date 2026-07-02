"""Unified ML pipeline orchestrator."""

import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

import structlog
from sklearn.preprocessing import MultiLabelBinarizer

from .classifier import TopicClassifier
from .clustering import HypotheticalClusterer
from .data import binarize_labels, extract_features, load_data
from .regressor import QualityRegressor

logger = structlog.get_logger(__name__)


class MLPipeline:
    """Coordinates classifier, regressor, and clusterer.

    `classifier_backend`: "tfidf" (default sklearn LinearSVC on TF-IDF) or
    "setfit" (contrastive Sentence-Transformers fine-tune). Env var
    `JIKAI_CLASSIFIER_BACKEND` overrides the constructor argument.
    """

    def __init__(
        self,
        models_dir: str = "models",
        classifier_backend: str | None = None,
    ):
        self.models_dir = models_dir
        env_backend = os.environ.get("JIKAI_CLASSIFIER_BACKEND")
        self.classifier_backend = (env_backend or classifier_backend or "tfidf").lower()
        if self.classifier_backend not in {"tfidf", "setfit"}:
            logger.warning(
                "Unknown classifier_backend, falling back to tfidf",
                requested=self.classifier_backend,
            )
            self.classifier_backend = "tfidf"
        self.classifier = TopicClassifier()
        self.setfit_classifier: Any = None
        if self.classifier_backend == "setfit":
            from .setfit_classifier import SetFitTopicClassifier

            self.setfit_classifier = SetFitTopicClassifier()
        self.regressor = QualityRegressor()
        self.clusterer = HypotheticalClusterer()
        self._vectorizer: Any = None
        self._binarizer: Optional[MultiLabelBinarizer] = None
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
        # optional setfit backend trained on the same split (kept alongside baseline)
        if self.classifier_backend == "setfit" and self.setfit_classifier is not None:
            _cb(0.35, "Training SetFit classifier (contrastive)")
            try:
                setfit_metrics = self.setfit_classifier.train(
                    train_df["text"].tolist(),
                    train_df["topic_list"].tolist(),
                    labels=list(self._binarizer.classes_),
                )
                setfit_eval = self.setfit_classifier.evaluate(
                    test_df["text"].tolist(), test_df["topic_list"].tolist()
                )
                cls_metrics["setfit"] = {**setfit_metrics, **setfit_eval}
            except Exception as exc:  # pragma: no cover — depends on setfit install
                logger.warning(
                    "SetFit training failed; falling back to TF-IDF classifier",
                    error=str(exc),
                )
                self.classifier_backend = "tfidf"
                self.setfit_classifier = None
        # regressor
        _cb(0.50, "Training regressor")
        self.regressor.train(X_train, train_df["quality_score"].values)
        reg_metrics = self.regressor.evaluate(X_test, test_df["quality_score"].values)
        # clusterer
        _cb(0.75, "Training clusterer")
        X_full, _ = extract_features(data["full"]["text"], vectorizer=self._vectorizer)
        self.clusterer.fit(X_full, n_clusters=n_clusters)
        _cb(0.90, "Saving models")
        self._save_all(data_path=data_path)
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
                X_train,
                train_df["quality_score"].values,
                progress_callback=progress_callback,
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
        result: Dict[str, Any] = {}
        if (
            self.classifier_backend == "setfit"
            and self.setfit_classifier is not None
            and self.setfit_classifier.is_trained
        ):
            result["topics"] = self.setfit_classifier.predict_topics([text])[0]
            result["classifier_backend"] = "setfit"
        elif self.classifier.is_trained and self._binarizer is not None:
            topics = self.classifier.predict_topics(X, list(self._binarizer.classes_))
            result["topics"] = topics[0]
            result["classifier_backend"] = "tfidf"
        if self.regressor.is_trained:
            result["quality"] = float(self.regressor.predict(X)[0])
        if self.clusterer.is_trained:
            result["cluster"] = self.clusterer.predict_cluster(X)
        return result

    def gate_confidence(self, text: str, requested_topics: list[str]) -> Dict[str, Any]:
        """Return per-topic confidence for the requested topics.

        Consumed by workflow_facade / hypothetical_service to enforce the ML
        gate: if the drafted hypothetical does not confidently cover the
        requested topics, the refine loop is triggered.

        Returns dict with keys: `per_topic` (float per requested), `min_confidence`,
        `mean_confidence`, `backend`.
        """
        per_topic: Dict[str, float] = {}
        backend = self.classifier_backend
        if (
            self.classifier_backend == "setfit"
            and self.setfit_classifier is not None
            and self.setfit_classifier.is_trained
        ):
            per_topic = self.setfit_classifier.predict_confidence(text, requested_topics)
        elif self.classifier.is_trained and self._binarizer is not None:
            X = self._vectorizer.transform([text])
            preds = self.classifier.predict_topics(X, list(self._binarizer.classes_))[0]
            per_topic = {t: (1.0 if t in preds else 0.0) for t in requested_topics}
            backend = "tfidf"
        else:
            per_topic = {t: 0.0 for t in requested_topics}
            backend = "unavailable"
        values = list(per_topic.values()) or [0.0]
        return {
            "per_topic": per_topic,
            "min_confidence": float(min(values)),
            "mean_confidence": float(sum(values) / len(values)),
            "backend": backend,
        }

    def evaluate_all(self) -> Dict:
        """Return cached metrics from last training."""
        return self._metrics

    def get_status(self) -> Dict:
        """Status of trained models and metrics."""
        return {
            "classifier_trained": self.classifier.is_trained,
            "setfit_trained": bool(
                self.setfit_classifier is not None and self.setfit_classifier.is_trained
            ),
            "classifier_backend": self.classifier_backend,
            "regressor_trained": self.regressor.is_trained,
            "clusterer_trained": self.clusterer.is_trained,
            "metrics": self._metrics,
        }

    def _save_all(self, data_path: str = ""):
        import joblib

        self.classifier.save_model(os.path.join(self.models_dir, "classifier.joblib"))
        self.regressor.save_model(os.path.join(self.models_dir, "regressor.joblib"))
        self.clusterer.save_model(os.path.join(self.models_dir, "clusterer.joblib"))
        joblib.dump(
            self._vectorizer, os.path.join(self.models_dir, "vectorizer.joblib")
        )
        joblib.dump(self._binarizer, os.path.join(self.models_dir, "binarizer.joblib"))
        if self.setfit_classifier is not None and self.setfit_classifier.is_trained:
            try:
                self.setfit_classifier.save_model(
                    os.path.join(self.models_dir, "setfit_sg_tort")
                )
            except Exception as exc:  # pragma: no cover
                logger.warning("SetFit save failed", error=str(exc))
        self._save_metadata(data_path)

    def _save_metadata(self, data_path: str = ""):
        """Save metadata.json alongside model files."""
        dataset_hash = ""
        if data_path and os.path.exists(data_path):
            with open(data_path, "rb") as f:
                dataset_hash = hashlib.sha256(f.read()).hexdigest()
        feature_count = 0
        if self._vectorizer is not None and hasattr(self._vectorizer, "vocabulary_"):
            feature_count = len(self._vectorizer.vocabulary_)
        metadata = {
            "schema_version": 2,
            "training_date": datetime.now(timezone.utc).isoformat(),
            "dataset_hash": dataset_hash,
            "dataset_path": data_path,
            "feature_count": feature_count,
            "classifier_trained": self.classifier.is_trained,
            "classifier_backend": self.classifier_backend,
            "setfit_trained": bool(
                self.setfit_classifier is not None and self.setfit_classifier.is_trained
            ),
            "regressor_trained": self.regressor.is_trained,
            "clusterer_trained": self.clusterer.is_trained,
            "metrics": self._metrics,
        }
        meta_path = os.path.join(self.models_dir, "metadata.json")
        with open(meta_path, "w") as f:
            json.dump(metadata, f, indent=2)
        logger.info("Model metadata saved", path=meta_path)

    def load_all(self):
        """Load all saved models."""
        import joblib

        clf_path = os.path.join(self.models_dir, "classifier.joblib")
        reg_path = os.path.join(self.models_dir, "regressor.joblib")
        clu_path = os.path.join(self.models_dir, "clusterer.joblib")
        vec_path = os.path.join(self.models_dir, "vectorizer.joblib")
        bin_path = os.path.join(self.models_dir, "binarizer.joblib")
        setfit_path = os.path.join(self.models_dir, "setfit_sg_tort")
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
        if os.path.isdir(setfit_path):
            try:
                if self.setfit_classifier is None:
                    from .setfit_classifier import SetFitTopicClassifier

                    self.setfit_classifier = SetFitTopicClassifier()
                self.setfit_classifier.load_model(setfit_path)
                # If the setfit backend loaded successfully, prefer it.
                self.classifier_backend = "setfit"
            except Exception as exc:  # pragma: no cover
                logger.warning(
                    "SetFit load failed; keeping tfidf backend", error=str(exc)
                )
