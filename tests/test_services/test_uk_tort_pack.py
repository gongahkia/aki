import json
from pathlib import Path

import pytest

from src.domain import get_domain_pack, resolve_domain_pack
from src.services.corpus_service import CorpusQuery, CorpusService
from src.services.hypothetical_service import GenerationRequest


def test_uk_tort_domain_pack_uses_manifest():
    pack = get_domain_pack("uk_tort")

    assert pack.manifest_path == "corpus/packs/uk_tort/manifest.json"
    assert pack.corpus_path == "corpus/clean/uk_tort/corpus.json"
    assert pack.raw_paths == ("corpus/raw/uk_tort",)
    assert pack.record_format == "tna_legaldocml_excerpt_v1"
    assert pack.jurisdiction.matches("United Kingdom")
    assert pack.jurisdiction.matches("England and Wales")
    assert pack.canonicalize_topic("assumption of responsibility") == "duty_of_care"
    assert pack.is_supported_topic("occupier's liability")
    assert "duty_of_care" in pack.prompt_overlay["topic_hints"]
    assert "vicarious_liability" in pack.validation_overlay["topic_keywords"]


def test_resolve_domain_pack_normalizes_uk_display_input():
    assert resolve_domain_pack("UK Tort").key == "uk_tort"


def test_generation_request_accepts_uk_jurisdiction_alias():
    request = GenerationRequest(
        topics=["duty of care"],
        corpus_pack="uk_tort",
        jurisdiction="England and Wales",
        subject="tort",
    )

    assert request.jurisdiction == "uk"
    assert request.subject == "tort"


@pytest.mark.asyncio
async def test_uk_tort_pack_loads_tna_sample_records():
    corpus_path = Path("corpus/clean/uk_tort/corpus.json")
    raw_records = json.loads(corpus_path.read_text(encoding="utf-8"))
    service = CorpusService()

    entries = await service.load_corpus(corpus_pack="uk_tort")

    assert len(entries) == len(raw_records) == 5
    assert all(entry.corpus_pack_key == "uk_tort" for entry in entries)
    assert all(entry.jurisdiction == "uk" for entry in entries)
    assert all(entry.subject == "tort" for entry in entries)
    assert all(
        entry.metadata["source"]["name"] == "The National Archives Find Case Law"
        for entry in entries
    )
    assert all(
        entry.metadata["license"]["redistribution_status"] == "restricted"
        for entry in entries
    )
    assert all(
        entry.metadata["license"]["computational_analysis_requires_permission"] is True
        for entry in entries
    )


@pytest.mark.asyncio
async def test_uk_tort_pack_can_be_queried_by_uk_jurisdiction(monkeypatch):
    service = CorpusService()
    service._corpus_indexed = False
    monkeypatch.setattr(service, "_ensure_background_indexing", lambda: None)

    results = await service.query_relevant_hypotheticals(
        CorpusQuery(
            topics=["vicarious_liability"],
            corpus_pack="uk_tort",
            jurisdiction="uk",
            subject="tort",
            sample_size=2,
        )
    )

    assert results
    assert all(entry.corpus_pack_key == "uk_tort" for entry in results)
    assert all(entry.jurisdiction == "uk" for entry in results)
    assert any("Morrison" in entry.metadata["case_name"] for entry in results)
