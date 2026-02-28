"""Tests for generation request model validation."""

import pytest

from src.services.hypothetical_service import GenerationRequest


def test_generation_request_allows_configured_law_domain():
    request = GenerationRequest(topics=["negligence"], law_domain="tort")
    assert request.law_domain == "tort"


def test_generation_request_rejects_unsupported_law_domain():
    with pytest.raises(ValueError):
        GenerationRequest(topics=["negligence"], law_domain="contract")
