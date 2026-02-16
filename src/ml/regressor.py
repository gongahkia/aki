"""Quality score regressor using sklearn ensemble methods."""

from typing import Callable, Dict, Optional

import joblib
import numpy as np
import structlog
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

logger = structlog.get_logger(__name__)


class QualityRegressor:
    """Quality score regressor."""

    def __init__(self):
        self.model: Optional[GradientBoostingRegressor] = None
        self.is_trained = False
        self._metrics: Dict = {}

    def train(self, X, y, progress_callback: Optional[Callable] = None):
        """Train regressor on feature matrix X and quality scores y."""
        if progress_callback:
            progress_callback(0.1, "Training quality regressor")
        self.model = GradientBoostingRegressor(
            n_estimators=100, max_depth=5, random_state=42
        )
        self.model.fit(X, y)
        self.is_trained = True
        if progress_callback:
            progress_callback(1.0, "Regressor trained")
        logger.info("Quality regressor trained", n_samples=X.shape[0])

    def predict(self, X) -> np.ndarray:
        """Predict quality scores."""
        if not self.is_trained or self.model is None:
            raise RuntimeError("Regressor not trained")
        return self.model.predict(X)

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
        joblib.dump(self.model, path)
        logger.info("Regressor saved", path=path)

    def load_model(self, path: str):
        self.model = joblib.load(path)
        self.is_trained = True
        logger.info("Regressor loaded", path=path)
