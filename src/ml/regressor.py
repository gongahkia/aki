"""Quality score regressor using sklearn ensemble methods."""

from typing import Callable, Dict, Optional

import joblib
import numpy as np
import structlog
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

logger = structlog.get_logger(__name__)

QUALITY_DIMENSIONS = ["topic_coverage", "complexity_match", "structural_completeness"]


class QualityRegressor:
    """Quality score regressor with per-dimension scoring."""

    def __init__(self):
        self.model: Optional[GradientBoostingRegressor] = None
        self.dimension_models: Dict[str, GradientBoostingRegressor] = {}
        self.is_trained = False
        self._metrics: Dict = {}

    def train(self, X, y, dimension_targets: Optional[Dict[str, np.ndarray]] = None, progress_callback: Optional[Callable] = None):
        """Train regressor on feature matrix X and quality scores y.

        Args:
            dimension_targets: optional dict mapping dimension name to target array
                               for per-dimension scoring (topic_coverage, complexity_match, structural_completeness)
        """
        if progress_callback:
            progress_callback(0.1, "Training quality regressor")
        self.model = GradientBoostingRegressor(
            n_estimators=100, max_depth=5, random_state=42
        )
        self.model.fit(X, y)
        if dimension_targets:
            for dim_name, dim_y in dimension_targets.items():
                if dim_name in QUALITY_DIMENSIONS:
                    m = GradientBoostingRegressor(n_estimators=50, max_depth=3, random_state=42)
                    m.fit(X, dim_y)
                    self.dimension_models[dim_name] = m
        self.is_trained = True
        if progress_callback:
            progress_callback(1.0, "Regressor trained")
        logger.info("Quality regressor trained", n_samples=X.shape[0], dimensions=list(self.dimension_models.keys()))

    def predict(self, X) -> np.ndarray:
        """Predict quality scores, clamped to [0.0, 1.0]."""
        if not self.is_trained or self.model is None:
            raise RuntimeError("Regressor not trained")
        raw = self.model.predict(X)
        return np.clip(raw, 0.0, 1.0)

    def predict_dimensions(self, X) -> Dict[str, float]:
        """Predict per-dimension scores for a single sample, clamped to [0.0, 1.0]."""
        overall = float(np.clip(self.predict(X)[0], 0.0, 1.0))
        result = {"overall": overall}
        for dim_name, m in self.dimension_models.items():
            raw = m.predict(X)
            result[dim_name] = float(np.clip(raw[0], 0.0, 1.0))
        for dim in QUALITY_DIMENSIONS:
            if dim not in result:
                result[dim] = overall  # fallback to overall if dimension model missing
        return result

    def evaluate(self, X, y) -> Dict:
        """Evaluate returning mse, r2, mae."""
        preds = self.predict(X)
        self._metrics = {
            "mse": float(mean_squared_error(y, preds)),
            "r2": float(r2_score(y, preds)),
            "mae": float(mean_absolute_error(y, preds)),
        }
        return self._metrics

    def save_model(self, path: str):
        data = {"model": self.model, "dimension_models": self.dimension_models}
        joblib.dump(data, path)
        logger.info("Regressor saved", path=path)

    def load_model(self, path: str):
        data = joblib.load(path)
        if isinstance(data, dict) and "model" in data:
            self.model = data["model"]
            self.dimension_models = data.get("dimension_models", {})
        else:
            self.model = data  # backwards compat with old single-model saves
            self.dimension_models = {}
        self.is_trained = True
        logger.info("Regressor loaded", path=path, dimensions=list(self.dimension_models.keys()))
