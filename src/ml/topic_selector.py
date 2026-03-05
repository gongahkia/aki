"""Topic-based corpus entry retrieval and ranking using TF-IDF similarity + classifier confidence."""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import structlog
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

logger = structlog.get_logger(__name__)


class TopicSelector:
    """Retrieves and ranks corpus entries by topic relevance."""

    def __init__(self):
        self._vectorizer: Optional[TfidfVectorizer] = None
        self._corpus_texts: List[str] = []
        self._corpus_entries: List[Dict] = []
        self._tfidf_matrix = None

    def fit(self, entries: List[Dict]) -> None:
        """Index corpus entries for retrieval. Each entry needs 'text' and 'topics' keys."""
        self._corpus_entries = entries
        self._corpus_texts = [e["text"] for e in entries]
        self._vectorizer = TfidfVectorizer(
            max_features=5000, ngram_range=(1, 2), stop_words="english"
        )
        self._tfidf_matrix = self._vectorizer.fit_transform(self._corpus_texts)
        logger.info("topic_selector fitted", entries=len(entries))

    def select(
        self,
        requested_topics: List[str],
        n_results: int = 5,
        classifier=None,
    ) -> List[Tuple[Dict, float]]:
        """Return top-N corpus entries ranked by combined topic overlap + TF-IDF similarity.

        Args:
            requested_topics: canonical topic keys the user wants
            n_results: max entries to return
            classifier: optional trained TopicClassifier for confidence scoring

        Returns:
            list of (entry_dict, score) tuples sorted by descending score
        """
        if (
            not self._corpus_entries
            or self._tfidf_matrix is None
            or self._vectorizer is None
        ):
            return []
        query_text = " ".join(requested_topics)
        query_vec = self._vectorizer.transform([query_text])
        tfidf_scores = cosine_similarity(query_vec, self._tfidf_matrix).flatten()
        requested_set = set(requested_topics)
        scored: List[Tuple[int, float]] = []
        for i, entry in enumerate(self._corpus_entries):
            entry_topics = set(entry.get("topics", []))
            overlap = len(entry_topics & requested_set)
            topic_score = overlap / max(len(requested_set), 1)
            classifier_score = 0.0
            if (
                classifier
                and hasattr(classifier, "is_trained")
                and classifier.is_trained
            ):
                try:
                    from .data import extract_features

                    X, _ = extract_features(
                        [entry["text"]], vectorizer=self._vectorizer
                    )
                    pred = classifier.model.predict(X)
                    label_names = getattr(classifier, "label_names", [])
                    if label_names is not None:
                        predicted_topics = {
                            label_names[j]
                            for j in range(len(label_names))
                            if pred[0][j] == 1
                        }
                        classifier_score = len(predicted_topics & requested_set) / max(
                            len(requested_set), 1
                        )
                except Exception:
                    pass
            combined = (
                0.4 * tfidf_scores[i] + 0.4 * topic_score + 0.2 * classifier_score
            )
            scored.append((i, combined))
        scored.sort(key=lambda x: x[1], reverse=True)
        results = []
        for idx, score in scored[:n_results]:
            results.append((self._corpus_entries[idx], score))
        return results
