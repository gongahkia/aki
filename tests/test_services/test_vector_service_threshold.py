"""Tests for semantic-search relevance threshold behavior."""

from unittest.mock import MagicMock

import pytest

from src.services.vector_service import VectorService


@pytest.mark.asyncio
async def test_semantic_search_returns_empty_when_top_similarity_below_threshold():
    service = VectorService()
    service._initialized = True
    service._collection = MagicMock()
    service._collection.count.return_value = 2
    service._collection.query.return_value = {
        "ids": [["a", "b"]],
        "documents": [["Doc A", "Doc B"]],
        "metadatas": [
            [
                {"topics": "negligence", "complexity": "basic"},
                {"topics": "defamation", "complexity": "basic"},
            ]
        ],
        "distances": [[10.0, 11.0]],
    }
    service._embed_text = lambda text: [0.1, 0.2]  # type: ignore[method-assign]

    results = await service.semantic_search(
        query_topics=["negligence"],
        n_results=2,
        min_similarity=0.20,
    )

    assert results == []


@pytest.mark.asyncio
async def test_semantic_search_filters_results_below_threshold():
    service = VectorService()
    service._initialized = True
    service._collection = MagicMock()
    service._collection.count.return_value = 3
    service._collection.query.return_value = {
        "ids": [["a", "b", "c"]],
        "documents": [["Doc A", "Doc B", "Doc C"]],
        "metadatas": [
            [
                {"topics": "negligence", "complexity": "basic"},
                {"topics": "duty of care", "complexity": "intermediate"},
                {"topics": "defamation", "complexity": "basic"},
            ]
        ],
        "distances": [[0.1, 0.4, 3.0]],
    }
    service._embed_text = lambda text: [0.1, 0.2]  # type: ignore[method-assign]

    results = await service.semantic_search(
        query_topics=["negligence"],
        n_results=3,
        min_similarity=0.50,
    )

    assert [entry["id"] for entry in results] == ["a", "b"]
    assert all(float(entry["similarity_score"]) >= 0.5 for entry in results)
