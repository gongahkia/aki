from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.config import settings
from src.services.corpus_service import CorpusQuery, CorpusService, HypotheticalEntry
from src.services.vector_service import VectorService


@pytest.mark.asyncio
async def test_hybrid_search_uses_bm25_when_dense_unavailable():
    service = VectorService()
    service._initialized = True
    service._fallback_mode = True
    documents = [
        {
            "id": "a",
            "text": "A negligence dispute about duty of care and breach.",
            "topics": ["negligence", "duty of care"],
            "metadata": {},
        },
        {
            "id": "b",
            "text": "A defamation dispute about publication.",
            "topics": ["defamation"],
            "metadata": {},
        },
    ]

    results = await service.hybrid_search(
        query_topics=["negligence", "duty of care"],
        corpus_documents=documents,
        n_results=1,
    )

    assert [result["id"] for result in results] == ["a"]
    assert results[0]["retrieval_mode"] == "hybrid"
    assert results[0]["lexical_score"] > 0


def test_reciprocal_rank_fusion_prefers_multi_branch_matches():
    scores = VectorService._reciprocal_rank_fusion(
        [["dense-only", "both"], ["both", "lexical-only"]],
        k=60,
    )

    assert scores["both"] > scores["dense-only"]
    assert scores["both"] > scores["lexical-only"]


def test_cross_encoder_reranker_is_optional(monkeypatch):
    service = VectorService()
    service._reranker_model = MagicMock()
    service._reranker_model.predict.return_value = [0.1, 0.9]
    original_model = settings.retrieval_reranker_model
    monkeypatch.setattr(settings, "retrieval_reranker_model", "test-reranker")

    try:
        results = service._rerank_with_cross_encoder(
            "negligence",
            [
                {"id": "a", "text": "weak"},
                {"id": "b", "text": "strong"},
            ],
            n_results=2,
        )
    finally:
        monkeypatch.setattr(settings, "retrieval_reranker_model", original_model)

    assert [result["id"] for result in results] == ["b", "a"]
    assert results[0]["reranker_score"] == 0.9


@pytest.mark.asyncio
async def test_corpus_service_hybrid_mode_uses_vector_hybrid_search(monkeypatch):
    service = CorpusService()
    service._corpus_indexed = False
    service._index_task = None
    service._vector_service = AsyncMock()
    service._vector_service.hybrid_search = AsyncMock(
        return_value=[
            {
                "id": "1",
                "text": "Negligence scenario in Singapore",
                "topics": ["negligence"],
                "corpus_pack_key": "sg_tort",
                "jurisdiction": "sg",
                "subject": "tort",
                "subtopics": [],
                "metadata": {},
                "retrieval_mode": "hybrid",
                "rrf_score": 0.03,
                "dense_score": None,
                "lexical_score": 2.0,
            }
        ]
    )
    monkeypatch.setattr(service, "_ensure_background_indexing", MagicMock())
    monkeypatch.setattr(
        service,
        "load_corpus",
        AsyncMock(
            return_value=[
                HypotheticalEntry(
                    id="1",
                    text="Negligence scenario in Singapore",
                    topics=["negligence"],
                )
            ]
        ),
    )
    monkeypatch.setattr(settings, "retrieval_mode", "hybrid")

    results = await service.query_relevant_hypotheticals(
        CorpusQuery(topics=["negligence"], sample_size=1)
    )

    assert [result.id for result in results] == ["1"]
    assert results[0].metadata["retrieval_mode"] == "hybrid"
    service._vector_service.hybrid_search.assert_awaited_once()


@pytest.fixture(autouse=True)
def _restore_retrieval_mode(monkeypatch):
    original_mode: Any = settings.retrieval_mode
    yield
    monkeypatch.setattr(settings, "retrieval_mode", original_mode)
