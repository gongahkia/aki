"""Tests for manifest-backed SG Tort corpus pack loading."""

import json
from pathlib import Path

import pytest

from src.domain import get_domain_pack
from src.services.corpus_service import CorpusQuery, CorpusService, HypotheticalEntry


def test_sg_tort_domain_pack_uses_reference_manifest():
    pack = get_domain_pack("sg_tort")

    assert pack.manifest_path == "corpus/packs/sg_tort/manifest.json"
    assert pack.corpus_path == "corpus/labelled/sg_tort/corpus.json"
    assert pack.supplemental_corpus_paths == ("corpus/contrib/sg_tort/corpus.json",)
    assert pack.raw_paths == ("corpus/raw/tort",)
    assert pack.record_format == "medallion_gold_v1"
    assert "negligence" in pack.topic_keys
    assert pack.canonicalize_topic("duty of care") == "duty_of_care"
    assert pack.topic_definitions is not None
    assert pack.prompt_overlay is not None
    assert pack.validation_overlay is not None
    assert pack.topic_definitions["negligence"].label == "Negligence"
    assert "limitation_periods" in pack.prompt_overlay["topic_hints"]
    assert "negligence" in pack.validation_overlay["topic_keywords"]


@pytest.mark.asyncio
async def test_sg_tort_pack_load_preserves_all_clean_corpus_records():
    corpus_path = Path("corpus/labelled/sg_tort/corpus.json")
    contrib_path = Path("corpus/contrib/sg_tort/corpus.json")
    raw_records = json.loads(corpus_path.read_text(encoding="utf-8"))
    contrib_records = json.loads(contrib_path.read_text(encoding="utf-8"))
    service = CorpusService()

    entries = await service.load_corpus(corpus_pack="sg_tort")

    assert len(entries) == len(raw_records) + len(contrib_records) == 121
    assert all(entry.corpus_pack_key == "sg_tort" for entry in entries)
    assert all(entry.jurisdiction == "sg" for entry in entries)
    assert all(entry.subject == "tort" for entry in entries)
    assert all(entry.text for entry in entries)
    seed_entries = [
        entry
        for entry in entries
        if entry.metadata.get("corpus_file") == str(corpus_path)
    ]
    contrib_entries = [
        entry
        for entry in entries
        if entry.metadata.get("corpus_file") == str(contrib_path)
    ]
    assert len(seed_entries) == 41
    assert len(contrib_entries) == 80
    assert all(entry.fact_pattern == entry.text for entry in seed_entries)
    assert all(entry.fact_pattern != entry.model_answer for entry in contrib_entries)
    assert all(entry.issues_expected or entry.model_answer for entry in contrib_entries)
    assert all(entry.answer_visibility == "hidden" for entry in contrib_entries)
    assert all("model_answer" not in entry.student_view() for entry in contrib_entries)


@pytest.mark.asyncio
async def test_sg_tort_pack_can_be_queried_by_runtime_scope(monkeypatch):
    service = CorpusService()
    service._corpus_indexed = False
    monkeypatch.setattr(service, "_ensure_background_indexing", lambda: None)

    results = await service.query_relevant_hypotheticals(
        CorpusQuery(
            topics=["negligence"],
            corpus_pack="sg_tort",
            jurisdiction="sg",
            subject="tort",
            sample_size=3,
        )
    )

    assert results
    assert all(entry.corpus_pack_key == "sg_tort" for entry in results)


@pytest.mark.asyncio
async def test_legacy_record_loads_into_student_schema_without_data_loss(tmp_path):
    corpus_path = tmp_path / "corpus.json"
    corpus_path.write_text(
        json.dumps(
            [
                {
                    "id": "legacy-1",
                    "text": "Advise A on negligence.",
                    "topic": ["negligence"],
                    "model_answer": "A should discuss duty, breach, and causation.",
                    "marking_rubric": {"issues": ["duty", "breach"]},
                }
            ]
        ),
        encoding="utf-8",
    )
    service = CorpusService()
    service._resolve_corpus_path = lambda _corpus_pack="sg_tort": corpus_path  # type: ignore[method-assign, assignment]
    service._resolve_corpus_paths = lambda _corpus_pack="sg_tort": [corpus_path]  # type: ignore[method-assign, assignment]

    entries = await service.load_corpus(corpus_pack="sg_tort")
    entry = entries[0]

    assert entry.text == "Advise A on negligence."
    assert entry.fact_pattern == entry.text
    assert entry.issues_expected == []
    assert entry.model_answer == "A should discuss duty, breach, and causation."
    assert "model_answer" not in entry.student_view()
    assert entry.student_view(include_model_answer=True)["model_answer"] == (
        "A should discuss duty, breach, and causation."
    )


@pytest.mark.asyncio
async def test_save_corpus_preserves_student_schema_fields(tmp_path):
    service = CorpusService()
    service._local_corpus_path = tmp_path / "corpus.json"
    entry = HypotheticalEntry(
        id="practice-1",
        text="Prompt plus facts",
        topics=["negligence"],
        question_prompt="Advise A.",
        fact_pattern="A slipped on wet stairs.",
        issues_expected=["duty", "breach", "causation"],
        model_answer="Discuss occupier negligence.",
        marking_rubric={"duty": 2},
        difficulty="medium",
        time_limit_minutes=30,
        jurisdiction_notes="SG law.",
        source_exam_context={"source_type": "authored"},
    )

    await service.save_corpus([entry])
    payload = json.loads(service._local_corpus_path.read_text(encoding="utf-8"))

    assert payload[0]["id"] == "practice-1"
    assert payload[0]["text"] == "Prompt plus facts"
    assert payload[0]["question_prompt"] == "Advise A."
    assert payload[0]["fact_pattern"] == "A slipped on wet stairs."
    assert payload[0]["issues_expected"] == ["duty", "breach", "causation"]
    assert payload[0]["model_answer"] == "Discuss occupier negligence."
    assert payload[0]["marking_rubric"] == {"duty": 2}
    assert payload[0]["answer_visibility"] == "hidden"
