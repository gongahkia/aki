"""Complexity controller: maps complexity tiers to generation constraints."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

import structlog

logger = structlog.get_logger(__name__)

TIER_DEFAULTS: Dict[int, "ComplexityConstraints"] = {}


@dataclass
class ComplexityConstraints:
    """Generation constraints for a complexity tier."""

    word_count_min: int
    word_count_max: int
    max_legal_issues: int
    sentence_complexity: str  # simple, moderate, complex
    vocabulary_level: str  # basic, intermediate, advanced


TIER_DEFAULTS = {
    1: ComplexityConstraints(300, 500, 2, "simple", "basic"),
    2: ComplexityConstraints(400, 700, 3, "simple", "basic"),
    3: ComplexityConstraints(600, 1000, 5, "moderate", "intermediate"),
    4: ComplexityConstraints(800, 1200, 7, "complex", "advanced"),
    5: ComplexityConstraints(1000, 1500, 10, "complex", "advanced"),
}


class ComplexityController:
    """Learns and outputs generation constraints per complexity tier."""

    def __init__(self):
        self.is_trained = False
        self._learned_tiers: Dict[int, ComplexityConstraints] = {}

    def train(
        self,
        texts: List[str],
        complexities: List[int],
        topics_per_entry: List[List[str]],
    ) -> Dict:
        """Learn constraints from labelled data by aggregating per tier."""
        tier_data: Dict[int, List] = {i: [] for i in range(1, 6)}
        for text, comp, topics in zip(texts, complexities, topics_per_entry):
            c = max(1, min(int(comp), 5))
            word_count = len(text.split())
            num_issues = len(topics)
            tier_data[c].append((word_count, num_issues))
        for tier, samples in tier_data.items():
            if not samples:
                self._learned_tiers[tier] = TIER_DEFAULTS[tier]
                continue
            word_counts = [s[0] for s in samples]
            issue_counts = [s[1] for s in samples]
            avg_words = int(sum(word_counts) / len(word_counts))
            avg_issues = int(sum(issue_counts) / len(issue_counts))
            margin = max(100, int(avg_words * 0.3))
            defaults = TIER_DEFAULTS[tier]
            self._learned_tiers[tier] = ComplexityConstraints(
                word_count_min=max(200, avg_words - margin),
                word_count_max=avg_words + margin,
                max_legal_issues=max(2, avg_issues + 2),
                sentence_complexity=defaults.sentence_complexity,
                vocabulary_level=defaults.vocabulary_level,
            )
        self.is_trained = True
        logger.info("complexity_controller trained", tiers=len(self._learned_tiers))
        return {"tiers": {k: v.word_count_max for k, v in self._learned_tiers.items()}}

    def calibrate_from_corpus(self, corpus_path: str) -> Dict:
        """Auto-calibrate difficulty tiers from corpus statistics."""
        import json
        from pathlib import Path
        corpus_file = Path(corpus_path)
        if not corpus_file.exists():
            logger.warning("corpus not found for calibration", path=corpus_path)
            return {}
        try:
            raw = json.loads(corpus_file.read_text(encoding="utf-8"))
            entries = raw if isinstance(raw, list) else raw.get("entries", raw.get("cases", []))
        except Exception as exc:
            logger.error("corpus parse failed during calibration", error=str(exc))
            return {}
        texts, complexities, topics_list = [], [], []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            text = str(entry.get("text", "")).strip()
            if not text:
                continue
            topics = entry.get("topics", [])
            if isinstance(topics, str):
                topics = [topics]
            word_count = len(text.split())
            inferred_complexity = 2 if word_count < 500 else (3 if word_count < 1000 else (4 if word_count < 1500 else 5))
            texts.append(text)
            complexities.append(inferred_complexity)
            topics_list.append(topics)
        if len(texts) >= 2:
            return self.train(texts, complexities, topics_list)
        return {}

    def get_constraints(self, complexity: int) -> ComplexityConstraints:
        """Return constraints for a complexity tier (1-5)."""
        c = max(1, min(int(complexity), 5))
        if self.is_trained and c in self._learned_tiers:
            return self._learned_tiers[c]
        return TIER_DEFAULTS[c]
