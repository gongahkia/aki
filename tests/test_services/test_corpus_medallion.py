import json
from pathlib import Path

from src.services import corpus_medallion


def _write_case(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _isolate_ingestion_side_effects(tmp_path, monkeypatch):
    real_quarantine_record = corpus_medallion.quarantine_record
    monkeypatch.setattr(corpus_medallion, "emit_event", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        corpus_medallion, "record_source_success", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(
        corpus_medallion, "record_source_failure", lambda *_args, **_kwargs: None
    )

    def quarantine_record(path, **kwargs):
        kwargs["events_path"] = tmp_path / "events.jsonl"
        return real_quarantine_record(path, **kwargs)

    monkeypatch.setattr(corpus_medallion, "quarantine_record", quarantine_record)


def test_medallion_pipeline_writes_provenance_and_is_idempotent(tmp_path, monkeypatch):
    _isolate_ingestion_side_effects(tmp_path, monkeypatch)
    raw_dir = tmp_path / "corpus" / "raw" / "tort"
    _write_case(raw_dir / "1.txt", "Negligence and duty of care. " * 4)
    _write_case(raw_dir / "2.txt", "Negligence and duty of care. " * 4)
    _write_case(raw_dir / "3.txt", "Private nuisance and land use. " * 4)
    manifest_path = tmp_path / "corpus" / "manifest.json"
    silver_path = tmp_path / "corpus" / "normalized" / "sg_tort" / "corpus.json"
    gold_path = tmp_path / "corpus" / "labelled" / "sg_tort" / "corpus.json"

    class Pack:
        key = "sg_tort"
        raw_paths = (str(raw_dir),)
        corpus_path = str(tmp_path / "corpus" / "clean" / "tort" / "corpus.json")
        manifest_path = "corpus/packs/sg_tort/manifest.json"
        jurisdiction_key = "sg"
        subject_key = "tort"

    monkeypatch.setattr(corpus_medallion, "resolve_domain_pack", lambda key: Pack())

    bronze = corpus_medallion.run_bronze(
        corpus_pack="sg_tort",
        manifest_path=manifest_path,
    )
    bronze_again = corpus_medallion.run_bronze(
        corpus_pack="sg_tort",
        manifest_path=manifest_path,
    )
    silver = corpus_medallion.run_silver(
        corpus_pack="sg_tort",
        manifest_path=manifest_path,
        output_path=silver_path,
    )
    gold = corpus_medallion.run_gold(
        corpus_pack="sg_tort",
        manifest_path=manifest_path,
        silver_path=silver_path,
        output_path=gold_path,
    )

    assert bronze.records_count == 3
    assert bronze_again.skipped is True
    assert silver.records_count == 2
    assert gold.records_count == 2

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == corpus_medallion.SCHEMA_VERSION
    assert manifest["records"][0]["source"]["url"].startswith("file://")
    assert manifest["records"][0]["source"]["retrieved_at"]

    gold_payload = json.loads(gold_path.read_text(encoding="utf-8"))
    assert gold_payload[0]["corpus_pack_key"] == "sg_tort"
    assert gold_payload[0]["jurisdiction"] == "sg"
    assert gold_payload[0]["metadata"]["provenance"]["source_url"].startswith("file://")


def test_silver_quarantines_invalid_source_without_corrupting_output(
    tmp_path, monkeypatch
):
    _isolate_ingestion_side_effects(tmp_path, monkeypatch)
    raw_dir = tmp_path / "corpus" / "raw" / "tort"
    valid_path = raw_dir / "1.txt"
    invalid_path = raw_dir / "2.txt"
    _write_case(valid_path, "Negligence and duty of care. " * 4)
    _write_case(invalid_path, "Private nuisance and land use. " * 4)
    manifest_path = tmp_path / "corpus" / "manifest.json"
    silver_path = tmp_path / "corpus" / "normalized" / "sg_tort" / "corpus.json"
    quarantine_path = (
        tmp_path / "corpus" / "normalized" / "sg_tort" / "quarantine.jsonl"
    )

    class Pack:
        key = "sg_tort"
        raw_paths = (str(raw_dir),)
        corpus_path = str(tmp_path / "corpus" / "clean" / "tort" / "corpus.json")
        manifest_path = "corpus/packs/sg_tort/manifest.json"
        jurisdiction_key = "sg"
        subject_key = "tort"

    monkeypatch.setattr(corpus_medallion, "resolve_domain_pack", lambda key: Pack())

    corpus_medallion.run_bronze(
        corpus_pack="sg_tort",
        manifest_path=manifest_path,
    )
    invalid_path.unlink()
    silver = corpus_medallion.run_silver(
        corpus_pack="sg_tort",
        manifest_path=manifest_path,
        output_path=silver_path,
        quarantine_path=quarantine_path,
    )

    assert silver.records_count == 1
    assert silver.quarantined_count == 1
    silver_payload = json.loads(silver_path.read_text(encoding="utf-8"))
    assert len(silver_payload) == 1
    assert silver_payload[0]["source"]["path"].endswith("1.txt")
    quarantine = [
        json.loads(line)
        for line in quarantine_path.read_text(encoding="utf-8").splitlines()
    ]
    assert quarantine[0]["source"].endswith("2")
    assert quarantine[0]["stage"] == "silver"
