"""Tests for manifest-backed SG Tort corpus pack loading."""

import json
from pathlib import Path

import pytest

from src.domain import get_domain_pack
from src.services.corpus_service import CorpusQuery, CorpusService


def test_sg_tort_domain_pack_uses_reference_manifest():
    pack = get_domain_pack("sg_tort")

    assert pack.manifest_path == "corpus/packs/sg_tort/manifest.json"
    assert pack.corpus_path == "corpus/clean/tort/corpus.json"
    assert pack.raw_paths == ("corpus/raw/tort",)
    assert pack.record_format == "legacy_text_topic_v1"
    assert "negligence" in pack.topic_keys
    assert pack.canonicalize_topic("duty of care") == "duty_of_care"
    assert pack.topic_definitions["negligence"].label == "Negligence"
    assert "limitation_periods" in pack.prompt_overlay["topic_hints"]
    assert "negligence" in pack.validation_overlay["topic_keywords"]


@pytest.mark.asyncio
async def test_sg_tort_pack_load_preserves_all_clean_corpus_records():
    corpus_path = Path("corpus/clean/tort/corpus.json")
    raw_records = json.loads(corpus_path.read_text(encoding="utf-8"))
    service = CorpusService()

    entries = await service.load_corpus(corpus_pack="sg_tort")

    assert len(entries) == len(raw_records) == 41
    assert all(entry.corpus_pack_key == "sg_tort" for entry in entries)
    assert all(entry.jurisdiction == "sg" for entry in entries)
    assert all(entry.subject == "tort" for entry in entries)
    assert all(entry.text for entry in entries)


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
