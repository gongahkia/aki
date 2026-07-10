import json
from pathlib import Path

import pytest

from src.domain import get_domain_pack, resolve_domain_pack
from src.services.corpus_service import CorpusQuery, CorpusService
from src.services.hypothetical_service import GenerationRequest


def test_us_tort_domain_pack_uses_manifest():
    pack = get_domain_pack("us_tort")

    assert pack.manifest_path == "corpus/packs/us_tort/manifest.json"
    assert pack.corpus_path == "corpus/clean/us_tort/corpus.json"
    assert pack.raw_paths == ("corpus/raw/us_tort",)
    assert pack.record_format == "cap_case_json_v1"
    assert pack.jurisdiction.matches("United States")
    assert pack.jurisdiction.matches("USA")
    assert pack.canonicalize_topic("proximate cause") == "causation"
    assert pack.is_supported_topic("comparative fault")
    assert pack.prompt_overlay is not None
    assert pack.validation_overlay is not None
    assert "product_liability" in pack.prompt_overlay["topic_hints"]
    assert "causation" in pack.validation_overlay["topic_keywords"]


def test_resolve_domain_pack_normalizes_display_input():
    assert resolve_domain_pack("US Tort").key == "us_tort"


def test_generation_request_accepts_us_jurisdiction_alias():
    request = GenerationRequest(
        topics=["proximate cause"],
        corpus_pack="us_tort",
        jurisdiction="United States",
        subject="tort",
    )

    assert request.jurisdiction == "us"
    assert request.subject == "tort"


@pytest.mark.asyncio
async def test_us_tort_pack_loads_cap_sample_records():
    corpus_path = Path("corpus/clean/us_tort/corpus.json")
    raw_records = json.loads(corpus_path.read_text(encoding="utf-8"))
    service = CorpusService()

    entries = await service.load_corpus(corpus_pack="us_tort")

    assert len(entries) == len(raw_records) == 5
    assert all(entry.corpus_pack_key == "us_tort" for entry in entries)
    assert all(entry.jurisdiction == "us" for entry in entries)
    assert all(entry.subject == "tort" for entry in entries)
    assert all(
        entry.metadata["source"]["name"] == "Caselaw Access Project"
        for entry in entries
    )
    assert all(
        entry.metadata["license"]["redistribution_status"] == "allowed"
        for entry in entries
    )


@pytest.mark.asyncio
async def test_us_tort_pack_can_be_queried_by_us_jurisdiction(monkeypatch):
    service = CorpusService()
    service._corpus_indexed = False
    monkeypatch.setattr(service, "_ensure_background_indexing", lambda: None)

    results = await service.query_relevant_hypotheticals(
        CorpusQuery(
            topics=["causation"],
            corpus_pack="us_tort",
            jurisdiction="us",
            subject="tort",
            sample_size=2,
        )
    )

    assert results
    assert all(entry.corpus_pack_key == "us_tort" for entry in results)
    assert all(entry.jurisdiction == "us" for entry in results)
    assert any(
        entry.metadata["case_abbreviation"] == "Summers v. Tice" for entry in results
    )
