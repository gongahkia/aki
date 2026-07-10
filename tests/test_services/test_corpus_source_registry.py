import json
from pathlib import Path

import pytest

from src.corpus_source_registry import (
    REGISTRY_PATH,
    REQUIRED_SOURCE_FIELDS,
    SourceRegistryError,
    assert_derived_metadata_allowed,
    assert_records_text_commit_allowed,
    assert_text_commit_allowed,
    load_source_registry,
)
from src.services.scraper_service import merge_into_corpus, save_scraped


def _registry_names_and_aliases() -> set[str]:
    names = set()
    for source in load_source_registry().values():
        names.add(source["name"])
        names.update(source.get("aliases", []))
    return names


def test_registry_entries_have_required_fields():
    registry = load_source_registry()

    assert "cap_static_case_json" in registry
    for source in registry.values():
        assert set(REQUIRED_SOURCE_FIELDS).issubset(source)


def test_registry_covers_pack_manifest_sources():
    names = _registry_names_and_aliases()
    for manifest_path in Path("corpus/packs").glob("*/manifest.json"):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for source in manifest["sources"]:
            assert source["name"] in names


def test_registry_covers_source_decision_sources():
    names = _registry_names_and_aliases()
    expected = {
        "SAL Journals Online",
        "Singapore Law Gazette",
        "Singapore Law Watch",
        "eLitigation.sg",
        "CommonLII",
        "Singapore Judiciary",
        "ASEAN Law Association SG chapter",
        "CAP terms",
        "CAP docs",
        "CourtListener terms",
        "CourtListener API docs",
        "Free Law API usage",
        "BAILII copyright page",
        "Find Case Law API docs",
        "Open Justice Licence v2.0",
        "High Court of Australia judgments",
        "Federal Court of Australia judgments",
        "NSW Caselaw",
        "Queensland Courts",
        "Supreme Court of Western Australia",
        "CALI Tort Law: A 21st-Century Approach",
        "Singapore Law Watch, Ch. 20 The Law of Negligence",
        "2Civility JumpStart sample Torts exam Q&A",
        "University of Washington Street Law tort hypotheticals",
        "Quimbee",
        "Studicata",
    }

    assert expected <= names


def test_text_commit_gate_allows_only_cleared_sources():
    assert_text_commit_allowed("cap_static_case_json")
    assert_text_commit_allowed("tna_find_case_law_xml")
    assert_derived_metadata_allowed("commonlii_sg")

    with pytest.raises(SourceRegistryError, match="not cleared"):
        assert_text_commit_allowed("commonlii_sg")

    with pytest.raises(SourceRegistryError, match="not registered"):
        assert_text_commit_allowed("missing_source")


def test_record_text_commit_gate_requires_registered_source_id():
    assert_records_text_commit_allowed(
        [{"id": "ok", "source": {"source_id": "cap_static_case_json"}}]
    )

    with pytest.raises(SourceRegistryError, match="no registered source_id"):
        assert_records_text_commit_allowed([{"id": "missing"}])


def test_scraper_text_writes_block_link_only_sources(tmp_path):
    entry = {
        "text": "negligence duty of care",
        "topic": ["negligence"],
        "metadata": {
            "source": "commonlii",
            "source_url": "http://www.commonlii.org/sg/cases/SGHC/2024/1.html",
            "title": "Example",
        },
    }

    with pytest.raises(SourceRegistryError, match="not cleared"):
        save_scraped([entry], out_dir=str(tmp_path / "raw"))

    with pytest.raises(SourceRegistryError, match="not cleared"):
        merge_into_corpus([entry], corpus_path=str(tmp_path / "corpus.json"))


def test_registry_path_points_to_json_file():
    assert REGISTRY_PATH.name == "source_registry.json"
    assert REGISTRY_PATH.exists()
