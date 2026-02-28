"""Tests for API topic canonicalization and tort-only guard."""

import pytest
from fastapi import HTTPException

from src.services.topic_guard import canonicalize_and_validate_topics


def test_api_topic_guard_rejects_non_tort_topics():
    with pytest.raises(HTTPException) as exc:
        canonicalize_and_validate_topics(["contract"])

    assert exc.value.status_code == 400


def test_api_topic_guard_canonicalizes_spaced_topics():
    canonical = canonicalize_and_validate_topics(["duty of care", "negligence"])
    assert canonical == ["duty_of_care", "negligence"]
