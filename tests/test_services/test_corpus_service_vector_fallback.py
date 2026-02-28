"""Tests for vector indexing guard and keyword fallback behavior."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.corpus_service import CorpusQuery, CorpusService, HypotheticalEntry


@pytest.mark.asyncio
async def test_keyword_fallback_used_when_index_not_ready(monkeypatch):
    service = CorpusService()
    service._corpus_indexed = False
    service._index_task = None
    service._vector_service = AsyncMock()
    service._vector_service.semantic_search = AsyncMock(return_value=[])
    service._ensure_background_indexing = MagicMock()
    service.load_corpus = AsyncMock(
        return_value=[
            HypotheticalEntry(
                id="1",
                text="Negligence scenario in Singapore",
                topics=["negligence", "duty_of_care"],
            )
        ]
    )

    query = CorpusQuery(topics=["negligence"], sample_size=1)
    results = await service.query_relevant_hypotheticals(query)

    assert len(results) == 1
    service._ensure_background_indexing.assert_called_once()
    service._vector_service.semantic_search.assert_not_called()


def test_background_indexing_guard_avoids_duplicate_tasks(monkeypatch):
    service = CorpusService()
    service._corpus_indexed = False

    class _PendingTask:
        def done(self):
            return False

    pending_task = _PendingTask()
    service._index_task = pending_task
    create_task = MagicMock()
    monkeypatch.setattr(asyncio, "create_task", create_task)

    service._ensure_background_indexing()

    create_task.assert_not_called()


@pytest.mark.asyncio
async def test_keyword_fallback_used_when_semantic_search_fails(monkeypatch):
    service = CorpusService()
    service._corpus_indexed = True
    service._vector_service = AsyncMock()
    service._vector_service.semantic_search = AsyncMock(
        side_effect=RuntimeError("vector init failed")
    )
    service.load_corpus = AsyncMock(
        return_value=[
            HypotheticalEntry(
                id="1",
                text="Battery and assault scenario in Singapore",
                topics=["battery", "assault"],
            )
        ]
    )

    query = CorpusQuery(topics=["battery"], sample_size=1)
    results = await service.query_relevant_hypotheticals(query)

    assert len(results) == 1
    assert results[0].id == "1"
