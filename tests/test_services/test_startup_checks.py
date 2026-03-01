"""Tests for startup prerequisite checks."""

import json

import pytest

from src import warmup
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
    corpus_path.write_text(
        '[{"text":"sample","topic":["negligence"]}]', encoding="utf-8"
    )

    validated = ensure_required_tort_corpus_file(corpus_path)

    assert validated == corpus_path


@pytest.fixture
def legacy_topic_corpus(tmp_path):
    corpus_path = tmp_path / "legacy_topic_corpus.json"
    corpus_path.write_text(
        json.dumps(
            [
                {"text": "A", "topic": ["negligence", "causation"]},
                {"text": "B", "topic": "duty of care"},
            ]
        ),
        encoding="utf-8",
    )
    return corpus_path


@pytest.fixture
def canonical_topics_corpus(tmp_path):
    corpus_path = tmp_path / "canonical_topics_corpus.json"
    corpus_path.write_text(
        json.dumps(
            [
                {"text": "A", "topics": ["battery", "assault"]},
                {"text": "B", "topics": "false imprisonment"},
            ]
        ),
        encoding="utf-8",
    )
    return corpus_path


def test_warmup_topic_extraction_supports_legacy_topic_field(
    monkeypatch, legacy_topic_corpus
):
    monkeypatch.setattr(warmup.settings, "corpus_path", str(legacy_topic_corpus))

    topics, elapsed_ms = warmup._load_corpus_topics()

    assert topics == ["causation", "duty of care", "negligence"]
    assert elapsed_ms >= 0.0


def test_warmup_topic_extraction_supports_canonical_topics_field(
    monkeypatch, canonical_topics_corpus
):
    monkeypatch.setattr(warmup.settings, "corpus_path", str(canonical_topics_corpus))

    topics, elapsed_ms = warmup._load_corpus_topics()

    assert topics == ["assault", "battery", "false imprisonment"]
    assert elapsed_ms >= 0.0
