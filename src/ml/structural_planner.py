"""Structural planner: predicts hypothetical skeleton from labelled structural elements."""

from __future__ import annotations

from typing import Dict, List, Optional

import structlog
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.multiclass import OneVsRestClassifier
from sklearn.preprocessing import MultiLabelBinarizer
from sklearn.svm import LinearSVC

logger = structlog.get_logger(__name__)

STRUCTURAL_ELEMENTS = [
    "parties",
    "scenario",
    "legal_issues",
    "analysis",
    "complications",
    "defences",
    "remedies",
    "timeline",
]


class StructuralPlanner:
    """Predicts the structural skeleton for a hypothetical given topics and complexity."""

    def __init__(self):
        self.is_trained = False
        self._vectorizer: Optional[TfidfVectorizer] = None
        self._binarizer = MultiLabelBinarizer(classes=STRUCTURAL_ELEMENTS)
        self._model: Optional[OneVsRestClassifier] = None

    def train(self, texts: List[str], structural_labels: List[List[str]]) -> Dict:
        """Train on labelled text->structural_elements mappings."""
        if len(texts) < 2:
            raise ValueError(f"Need at least 2 samples, got {len(texts)}")
        self._vectorizer = TfidfVectorizer(
            max_features=3000, ngram_range=(1, 2), stop_words="english"
        )
        X = self._vectorizer.fit_transform(texts)
        y = self._binarizer.fit_transform(structural_labels)
        self._model = OneVsRestClassifier(LinearSVC(dual="auto", max_iter=5000))
        self._model.fit(X, y)
        self.is_trained = True
        logger.info("structural_planner trained", samples=len(texts))
        return {"samples": len(texts), "elements": STRUCTURAL_ELEMENTS}

    def predict(self, text: str, topics: List[str], complexity: int = 3) -> Dict:
        """Predict structural skeleton for a hypothetical.

        Returns dict with:
            party_roles: suggested party count/types
            scenario_type: single-event, multi-event, etc.
            legal_issues_sequence: ordered list of topics to address
            analysis_points: structural elements present
        """
        if not self.is_trained or self._model is None or self._vectorizer is None:
            return self._default_plan(topics, complexity)
        combined = text + " " + " ".join(topics)
        X = self._vectorizer.transform([combined])
        pred = self._model.predict(X)
        elements = self._binarizer.inverse_transform(pred)[0]
        if not elements:
            elements = ("parties", "scenario", "legal_issues")
        num_issues = len(topics)
        party_count = max(2, min(complexity, 5))
        scenario_type = "multi-event" if num_issues > 3 else "single-event"
        return {
            "party_roles": party_count,
            "scenario_type": scenario_type,
            "legal_issues_sequence": list(topics),
            "analysis_points": list(elements),
        }

    def _default_plan(self, topics: List[str], complexity: int) -> Dict:
        """Fallback structural plan when model is untrained."""
        base_elements = ["parties", "scenario", "legal_issues"]
        if complexity >= 3:
            base_elements.append("complications")
        if complexity >= 4:
            base_elements.extend(["defences", "timeline"])
        return {
            "party_roles": max(2, min(complexity, 5)),
            "scenario_type": "multi-event" if len(topics) > 3 else "single-event",
            "legal_issues_sequence": list(topics),
            "analysis_points": base_elements,
        }
