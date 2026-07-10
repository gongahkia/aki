import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.corpus_service import CorpusQuery, CorpusService, HypotheticalEntry
from src.services.synthetic_expansion import (
    build_synthetic_review_queue,
    mark_record_reviewed,
    promote_reviewed_synthetic_records,
)


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_synthetic_review_queue_uses_authorities_and_marks_pending(tmp_path):
    output_path = tmp_path / "review_queue.json"

    result = build_synthetic_review_queue(
        topics=["defamation"],
        output_path=output_path,
        existing_corpus_paths=[],
        max_per_topic=1,
    )

    records = _load(output_path)
    record = records[0]
    assert result.records_count == 1
    assert record["metadata"]["synthetic_status"] == "generated_pending_review"
    assert record["metadata"]["generated_reviewed"] is False
    assert record["metadata"]["retrieval_eligible"] is False
    assert record["source_exam_context"]["review_status"] == "pending"
    assert record["metadata"]["authority_sources"][0]["citation"]
    assert "Review Publishing" in record["model_answer"]


def test_synthetic_novelty_blocks_near_duplicates(tmp_path):
    seed_path = tmp_path / "seed.json"
    first_path = tmp_path / "first.json"
    second_path = tmp_path / "second.json"
    build_synthetic_review_queue(
        topics=["defamation"],
        output_path=first_path,
        existing_corpus_paths=[],
        max_per_topic=1,
    )
    seed_path.write_text(first_path.read_text(encoding="utf-8"), encoding="utf-8")

    result = build_synthetic_review_queue(
        topics=["defamation"],
        output_path=second_path,
        existing_corpus_paths=[seed_path],
        max_per_topic=1,
        novelty_threshold=0.99,
    )

    assert result.records_count == 0
    assert result.rejected_count == 1
    assert _load(second_path) == []


def test_promote_reviewed_synthetic_records_only_allows_reviewed(tmp_path):
    queue_path = tmp_path / "review_queue.json"
    gold_path = tmp_path / "gold.json"
    output_path = tmp_path / "promoted.json"
    build_synthetic_review_queue(
        topics=["defamation"],
        output_path=queue_path,
        existing_corpus_paths=[],
        max_per_topic=1,
    )
    gold_path.write_text("[]\n", encoding="utf-8")

    pending = promote_reviewed_synthetic_records(
        review_queue_path=queue_path,
        gold_path=gold_path,
        output_path=output_path,
    )
    assert pending.promoted_count == 0
    assert _load(output_path) == []

    records = _load(queue_path)
    records[0] = mark_record_reviewed(records[0], reviewer="reviewer@example.test")
    queue_path.write_text(
        json.dumps(records, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    reviewed = promote_reviewed_synthetic_records(
        review_queue_path=queue_path,
        gold_path=gold_path,
        output_path=output_path,
    )

    promoted = _load(output_path)
    assert reviewed.promoted_count == 1
    assert promoted[0]["metadata"]["synthetic_status"] == "generated_reviewed"
    assert promoted[0]["metadata"]["generated_reviewed"] is True
    assert promoted[0]["metadata"]["retrieval_eligible"] is True


@pytest.mark.asyncio
async def test_unreviewed_synthetic_records_do_not_enter_default_retrieval(
    monkeypatch,
):
    pending = HypotheticalEntry(
        id="pending",
        text="Defamation scenario pending review",
        topics=["defamation"],
        metadata={
            "synthetic_status": "generated_pending_review",
            "generated_reviewed": False,
            "review_status": "pending",
            "generator": "repo_topic_template_v1",
        },
        source_exam_context={
            "synthetic_status": "generated_pending_review",
            "generated_reviewed": False,
        },
    )
    reviewed = HypotheticalEntry(
        id="reviewed",
        text="Defamation scenario reviewed by a human",
        topics=["defamation"],
        metadata={
            "synthetic_status": "generated_reviewed",
            "generated_reviewed": True,
            "review_status": "reviewed",
            "generator": "repo_topic_template_v1",
        },
        source_exam_context={
            "synthetic_status": "generated_reviewed",
            "generated_reviewed": True,
        },
    )
    service = CorpusService()
    service._corpus_indexed = False
    mock_ensure = MagicMock()
    monkeypatch.setattr(service, "_ensure_background_indexing", mock_ensure)
    monkeypatch.setattr(
        service, "load_corpus", AsyncMock(return_value=[pending, reviewed])
    )

    results = await service.query_relevant_hypotheticals(
        CorpusQuery(topics=["defamation"], sample_size=5)
    )

    assert [entry.id for entry in results] == ["reviewed"]


@pytest.mark.asyncio
async def test_unreviewed_synthetic_vector_results_are_filtered(monkeypatch):
    service = CorpusService()
    service._corpus_indexed = True
    service._vector_service = AsyncMock()
    service._vector_service.semantic_search = AsyncMock(
        return_value=[
            {
                "id": "pending",
                "text": "Pending generated defamation scenario",
                "topics": ["defamation"],
                "metadata": {
                    "synthetic_status": "generated_pending_review",
                    "generated_reviewed": False,
                    "review_status": "pending",
                    "generator": "repo_topic_template_v1",
                },
            },
            {
                "id": "reviewed",
                "text": "Reviewed generated defamation scenario",
                "topics": ["defamation"],
                "metadata": {
                    "synthetic_status": "generated_reviewed",
                    "generated_reviewed": True,
                    "review_status": "reviewed",
                    "generator": "repo_topic_template_v1",
                },
            },
        ]
    )
    monkeypatch.setattr(service, "load_corpus", AsyncMock(return_value=[]))

    results = await service.query_relevant_hypotheticals(
        CorpusQuery(topics=["defamation"], sample_size=5)
    )

    assert [entry.id for entry in results] == ["reviewed"]
