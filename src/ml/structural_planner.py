"""Structural planner: rule-based hypothetical skeleton from topics and complexity."""

from __future__ import annotations

from typing import Dict, List

import structlog

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
    """Predicts the structural skeleton for a hypothetical given topics and complexity.
    Uses rule-based heuristics (ML training removed — no labeled data available)."""

    def __init__(self):
        self.is_trained = False # kept for interface compat

    def predict(self, text: str, topics: List[str], complexity: int = 3) -> Dict:
        """Return structural plan based on topic count and complexity tier."""
        num_issues = len(topics)
        party_count = max(2, min(complexity, 5))
        base_elements = ["parties", "scenario", "legal_issues"]
        if complexity >= 3:
            base_elements.append("complications")
        if complexity >= 4:
            base_elements.extend(["defences", "timeline"])
        if complexity >= 5 or num_issues >= 4:
            base_elements.extend(e for e in ["remedies", "analysis"] if e not in base_elements)
        return {
            "party_roles": party_count,
            "scenario_type": "multi-event" if num_issues > 3 else "single-event",
            "legal_issues_sequence": list(topics),
            "analysis_points": base_elements,
        }
