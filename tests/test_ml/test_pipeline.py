"""Tests for ML pipeline."""

import csv

import pytest


@pytest.fixture
def sample_csv(tmp_path):
    """Create a small labelled CSV for testing."""
    path = tmp_path / "sample.csv"
    rows = [
        {
            "text": f"This is a test hypothetical about negligence and duty of care scenario {i}.",
            "topic_labels": "negligence|duty_of_care",
            "quality_score": 7.5,
            "difficulty_level": "medium",
        }
        for i in range(20)
    ]
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["text", "topic_labels", "quality_score", "difficulty_level"]
        )
        writer.writeheader()
        writer.writerows(rows)
    return str(path)


class TestMLPipeline:
    def test_train_all(self, sample_csv, tmp_path):
        from src.ml.pipeline import MLPipeline

        pipeline = MLPipeline(models_dir=str(tmp_path / "models"))
        metrics = pipeline.train_all(sample_csv, n_clusters=2)
        assert "classifier" in metrics
        assert "regressor" in metrics
        assert pipeline.classifier.is_trained
        assert pipeline.regressor.is_trained
        assert pipeline.clusterer.is_trained

    def test_predict(self, sample_csv, tmp_path):
        from src.ml.pipeline import MLPipeline

        pipeline = MLPipeline(models_dir=str(tmp_path / "models"))
        pipeline.train_all(sample_csv, n_clusters=2)
        result = pipeline.predict("This is about negligence and duty of care.")
        assert "topics" in result
        assert "quality" in result

    def test_get_status(self, sample_csv, tmp_path):
        from src.ml.pipeline import MLPipeline

        pipeline = MLPipeline(models_dir=str(tmp_path / "models"))
        pipeline.train_all(sample_csv, n_clusters=2)
        status = pipeline.get_status()
        assert status["classifier_trained"] is True

    def test_load_all(self, sample_csv, tmp_path):
        from src.ml.pipeline import MLPipeline

        models_dir = str(tmp_path / "models")
        pipeline = MLPipeline(models_dir=models_dir)
        pipeline.train_all(sample_csv, n_clusters=2)
        pipeline2 = MLPipeline(models_dir=models_dir)
        pipeline2.load_all()
        assert pipeline2.classifier.is_trained
