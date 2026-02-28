"""Tests for generation request model validation."""

import pytest

from src.services.hypothetical_service import GenerationRequest


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
