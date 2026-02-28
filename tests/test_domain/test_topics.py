"""Tests for canonical tort-topic registry."""

from src.domain.topics import TORT_TOPICS, canonicalize_topic, is_tort_topic


def test_registry_contains_expected_core_topics():
    assert "negligence" in TORT_TOPICS
    assert "duty_of_care" in TORT_TOPICS
    assert "volenti_non_fit_injuria" in TORT_TOPICS


def test_canonicalize_topic_handles_space_underscore_variants():
    assert canonicalize_topic("duty of care") == "duty_of_care"
    assert canonicalize_topic("duty_of_care") == "duty_of_care"
    assert canonicalize_topic("RYLANDS V FLETCHER") == "rylands_v_fletcher"


def test_is_tort_topic_uses_aliases():
    assert is_tort_topic("false imprisonment")
    assert is_tort_topic("false_imprisonment")
    assert not is_tort_topic("contract")
