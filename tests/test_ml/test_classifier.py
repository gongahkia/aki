"""Tests for ML classifier."""

import numpy as np
import pytest
from scipy.sparse import csr_matrix


@pytest.fixture
def small_dataset():
    """Small fixture dataset for testing."""
    X = csr_matrix(np.random.rand(20, 50))
    y = np.zeros((20, 3), dtype=int)
    for i in range(20):
        y[i, i % 3] = 1
    return X, y


class TestTopicClassifier:
    def test_train_and_predict(self, small_dataset):
        from src.ml.classifier import TopicClassifier

        X, y = small_dataset
        clf = TopicClassifier()
        clf.train(X, y)
        assert clf.is_trained
        preds = clf.predict(X)
        assert preds.shape == y.shape

    def test_evaluate(self, small_dataset):
        from src.ml.classifier import TopicClassifier

        X, y = small_dataset
        clf = TopicClassifier()
        clf.train(X, y)
        metrics = clf.evaluate(X, y, label_names=["a", "b", "c"])
        assert "micro_f1" in metrics
        assert "per_topic" in metrics

    def test_predict_topics(self, small_dataset):
        from src.ml.classifier import TopicClassifier

        X, y = small_dataset
        clf = TopicClassifier()
        clf.train(X, y)
        topics = clf.predict_topics(X[:1], ["a", "b", "c"])
        assert isinstance(topics, list)
        assert isinstance(topics[0], list)

    def test_save_load(self, small_dataset, tmp_path):
        from src.ml.classifier import TopicClassifier

        X, y = small_dataset
        clf = TopicClassifier()
        clf.train(X, y)
        path = str(tmp_path / "clf.joblib")
        clf.save_model(path)
        clf2 = TopicClassifier()
        clf2.load_model(path)
        assert clf2.is_trained
        preds = clf2.predict(X)
        assert preds.shape == y.shape
