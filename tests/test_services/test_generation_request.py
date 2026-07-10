"""Tests for generation request model validation."""

import pytest

from src.services.hypothetical_service import GenerationRequest
from src.domain import (
    TOPIC_ALIASES,
    DomainPack,
    Jurisdiction,
    all_tort_topic_keys,
    canonicalize_topic,
    is_tort_topic,
    register_domain_pack,
)


def test_generation_request_allows_configured_law_domain():
    request = GenerationRequest(topics=["negligence"], law_domain="tort")
    assert request.law_domain == "tort"


def test_generation_request_rejects_unsupported_law_domain():
    with pytest.raises(ValueError):
        GenerationRequest(topics=["negligence"], law_domain="contract")


def test_generation_request_normalizes_complexity_level():
    request = GenerationRequest(topics=["negligence"], complexity_level="4")
    assert request.complexity_level == "advanced"


def test_generation_request_rejects_unknown_complexity_level():
    with pytest.raises(ValueError):
        GenerationRequest(topics=["negligence"], complexity_level="impossible")


def test_generation_request_include_analysis_defaults_true():
    request = GenerationRequest(topics=["negligence"])
    assert request.include_analysis is True


def test_generation_request_defaults_to_issue_spotting_mode():
    request = GenerationRequest(topics=["negligence"])
    assert request.practice_mode == "issue_spotting"


def test_generation_request_normalizes_practice_mode():
    request = GenerationRequest(
        topics=["negligence"], practice_mode="progressive-hints"
    )
    assert request.practice_mode == "progressive_hints"


def test_generation_request_rejects_unknown_practice_mode():
    with pytest.raises(ValueError):
        GenerationRequest(topics=["negligence"], practice_mode="flashcards")


def test_generation_request_defaults_to_sg_tort_pack():
    request = GenerationRequest(topics=["negligence"])

    assert request.corpus_pack == "sg_tort"
    assert request.jurisdiction == "sg"
    assert request.subject == "tort"
    assert request.law_domain == "tort"


def test_generation_request_allows_registered_fake_jurisdiction_pack():
    register_domain_pack(
        DomainPack(
            key="test_tort",
            display_name="Testland Tort Law",
            jurisdiction=Jurisdiction(
                key="test",
                display_name="Testland",
                aliases=("testland",),
            ),
            law_domain="tort",
            canonicalize_topic=canonicalize_topic,
            is_supported_topic=is_tort_topic,
            topic_keys=all_tort_topic_keys(),
            topic_aliases=dict(TOPIC_ALIASES),
            subject_label="Tort Law",
        )
    )

    request = GenerationRequest(
        topics=["negligence"],
        corpus_pack="test_tort",
        jurisdiction="testland",
        subject="tort",
        law_domain="tort",
    )

    assert request.corpus_pack == "test_tort"
    assert request.jurisdiction == "test"
