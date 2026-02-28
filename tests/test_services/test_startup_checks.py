"""Tests for startup prerequisite checks."""

import pytest

from src.services.startup_checks import (
    StartupCheckError,
    ensure_required_tort_corpus_file,
)


def test_startup_check_fails_when_corpus_missing(tmp_path):
    missing_path = tmp_path / "missing.json"

    with pytest.raises(StartupCheckError) as exc_info:
        ensure_required_tort_corpus_file(missing_path)

    assert "make preprocess" in str(exc_info.value)


def test_startup_check_fails_when_corpus_empty_file(tmp_path):
    corpus_path = tmp_path / "corpus.json"
    corpus_path.write_text("", encoding="utf-8")

    with pytest.raises(StartupCheckError):
        ensure_required_tort_corpus_file(corpus_path)


def test_startup_check_fails_on_invalid_json(tmp_path):
    corpus_path = tmp_path / "corpus.json"
    corpus_path.write_text("{not-json", encoding="utf-8")

    with pytest.raises(StartupCheckError):
        ensure_required_tort_corpus_file(corpus_path)


def test_startup_check_passes_on_valid_nonempty_corpus(tmp_path):
    corpus_path = tmp_path / "corpus.json"
    corpus_path.write_text('[{"text":"sample","topic":["negligence"]}]', encoding="utf-8")

    validated = ensure_required_tort_corpus_file(corpus_path)

    assert validated == corpus_path
