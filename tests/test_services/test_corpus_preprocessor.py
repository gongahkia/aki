"""Tests for corpus preprocessing scan behavior."""

from pathlib import Path

from src.services.corpus_preprocessor import scan_raw_directory


def _write_case(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_scan_raw_directory_defaults_to_tort_only(tmp_path):
    raw_dir = tmp_path / "raw"
    _write_case(raw_dir / "tort" / "1.txt", "T" * 80)
    _write_case(raw_dir / "contract" / "1.txt", "C" * 80)

    entries = scan_raw_directory(raw_dir=raw_dir)
    source_dirs = {entry["metadata"]["source_dir"] for entry in entries}

    assert source_dirs == {"tort"}


def test_scan_raw_directory_includes_non_tort_when_opted_in(tmp_path):
    raw_dir = tmp_path / "raw"
    _write_case(raw_dir / "tort" / "1.txt", "T" * 80)
    _write_case(raw_dir / "contract" / "1.txt", "C" * 80)

    entries = scan_raw_directory(raw_dir=raw_dir, include_non_tort=True)
    source_dirs = {entry["metadata"]["source_dir"] for entry in entries}

    assert source_dirs == {"tort", "contract"}
