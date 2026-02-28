"""Tests for corpus preprocessing scan behavior."""

import json
from pathlib import Path

from src.services.corpus_preprocessor import build_corpus, scan_raw_directory


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


def test_build_corpus_defaults_to_tort_only(tmp_path):
    raw_dir = tmp_path / "raw"
    output_path = tmp_path / "clean" / "corpus.json"
    _write_case(raw_dir / "tort" / "t1.txt", "T" * 80)
    _write_case(raw_dir / "contract" / "c1.txt", "C" * 80)

    count = build_corpus(raw_dir=raw_dir, output_path=output_path)

    assert count == 1
    with open(output_path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    assert {entry["metadata"]["source_dir"] for entry in payload} == {"tort"}


def test_build_corpus_include_non_tort_opt_in(tmp_path):
    raw_dir = tmp_path / "raw"
    output_path = tmp_path / "clean" / "corpus.json"
    _write_case(raw_dir / "tort" / "t1.txt", "T" * 80)
    _write_case(raw_dir / "contract" / "c1.txt", "C" * 80)

    count = build_corpus(
        raw_dir=raw_dir,
        output_path=output_path,
        include_non_tort=True,
    )

    assert count == 2
    with open(output_path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    assert {entry["metadata"]["source_dir"] for entry in payload} == {
        "tort",
        "contract",
    }
