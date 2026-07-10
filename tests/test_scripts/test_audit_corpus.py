import json
import subprocess
import sys
from pathlib import Path


def _write_corpus(tmp_path: Path, record: dict) -> None:
    corpus_path = tmp_path / "corpus" / "labelled" / "sg_tort" / "corpus.json"
    corpus_path.parent.mkdir(parents=True)
    corpus_path.write_text(json.dumps([record]), encoding="utf-8")


def _valid_record() -> dict:
    return {
        "id": "sg_tort:test",
        "text": "Advise the parties on negligence. You may assume Singapore law applies.",
        "topics": ["negligence"],
        "corpus_pack_key": "sg_tort",
        "jurisdiction": "sg",
        "subject": "tort",
        "source": {"source_format": "repo_fixture", "url": "file://fixture"},
        "provenance": {"source_url": "file://fixture"},
        "license": {"name": "repository_fixture"},
    }


def _run_audit(tmp_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "script/audit_corpus.py", "--root", str(tmp_path)],
        check=False,
        cwd=Path(__file__).resolve().parents[2],
        text=True,
        capture_output=True,
    )


def test_audit_corpus_accepts_valid_record(tmp_path):
    _write_corpus(tmp_path, _valid_record())

    result = _run_audit(tmp_path)

    assert result.returncode == 0
    assert "By pack" in result.stdout
    assert "sg_tort: 1" in result.stdout
    assert "kind=hypo" in result.stdout


def test_audit_corpus_fails_missing_required_field(tmp_path):
    record = _valid_record()
    record.pop("source")
    _write_corpus(tmp_path, record)

    result = _run_audit(tmp_path)

    assert result.returncode == 1
    assert "missing required field 'source'" in result.stdout


def test_audit_corpus_fails_noncanonical_topic(tmp_path):
    record = _valid_record()
    record["topics"] = ["defence_of_consent"]
    _write_corpus(tmp_path, record)

    result = _run_audit(tmp_path)

    assert result.returncode == 1
    assert "is not canonical" in result.stdout
    assert "consent_defence" in result.stdout
