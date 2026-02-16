"""Tests for ML regressor."""
import pytest
import numpy as np
from scipy.sparse import csr_matrix


@pytest.fixture
def regression_dataset():
    X = csr_matrix(np.random.rand(20, 50))
    y = np.random.uniform(1.0, 10.0, 20)
    return X, y


class TestQualityRegressor:
    def test_train_and_predict(self, regression_dataset):
        from src.ml.regressor import QualityRegressor
        X, y = regression_dataset
        reg = QualityRegressor()
        reg.train(X, y)
        assert reg.is_trained
        preds = reg.predict(X)
        assert len(preds) == 20

    def test_evaluate(self, regression_dataset):
        from src.ml.regressor import QualityRegressor
        X, y = regression_dataset
        reg = QualityRegressor()
        reg.train(X, y)
        metrics = reg.evaluate(X, y)
        assert "mse" in metrics
        assert "r2" in metrics
        assert "mae" in metrics

    def test_save_load(self, regression_dataset, tmp_path):
        from src.ml.regressor import QualityRegressor
        X, y = regression_dataset
        reg = QualityRegressor()
        reg.train(X, y)
        path = str(tmp_path / "reg.joblib")
        reg.save_model(path)
        reg2 = QualityRegressor()
        reg2.load_model(path)
        assert reg2.is_trained
