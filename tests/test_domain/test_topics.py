"""Tests for canonical tort-topic registry."""

import pytest

from src.domain.packs import resolve_domain_pack
from src.domain.topics import TORT_TOPICS, canonicalize_topic, is_tort_topic


def test_registry_contains_expected_core_topics():
    assert "negligence" in TORT_TOPICS
    assert "duty_of_care" in TORT_TOPICS
    assert "volenti_non_fit_injuria" in TORT_TOPICS


def test_canonicalize_topic_handles_space_underscore_variants():
    assert canonicalize_topic("duty of care") == "duty_of_care"
    assert canonicalize_topic("duty_of_care") == "duty_of_care"
    assert canonicalize_topic("RYLANDS V FLETCHER") == "rylands_v_fletcher"


@pytest.mark.parametrize(
    "legacy,canonical",
    [
        ("defence_of_consent", "consent_defence"),
        ("defence_of_contributory_negligence", "contributory_negligence"),
        ("defence_of_illegality", "illegality_defence"),
        (
            "wilkinson_v_downton_tort_of_mental_infliction",
            "intentional_infliction_of_mental_harm",
        ),
    ],
)
def test_canonicalize_topic_handles_legacy_corpus_labels(legacy, canonical):
    assert canonicalize_topic(legacy) == canonical


def test_sg_pack_canonicalizes_legacy_corpus_labels():
    pack = resolve_domain_pack("sg_tort")

    assert pack.canonicalize_topic("defence_of_consent") == "consent_defence"
    assert (
        pack.canonicalize_topic("wilkinson_v_downton_tort_of_mental_infliction")
        == "intentional_infliction_of_mental_harm"
    )


def test_is_tort_topic_uses_aliases():
    assert is_tort_topic("false imprisonment")
    assert is_tort_topic("false_imprisonment")
    assert not is_tort_topic("contract")


@pytest.mark.parametrize(
    "canonical,alias",
    [
        (definition.key, alias)
        for definition in TORT_TOPICS.values()
        for alias in (
            definition.key,
            definition.key.replace("_", " "),
            *definition.aliases,
        )
    ],
)
def test_canonicalize_topic_fuzz_alias_separator_variants(canonical, alias):
    normalized_alias = alias.replace("-", " ").replace("_", " ")
    parts = [part for part in normalized_alias.split() if part]
    separators = [" ", "_", "-", "  "]
    case_styles = [str.lower, str.upper, str.title]
    variants = set()

    for separator in separators:
        joined = separator.join(parts)
        for transform in case_styles:
            candidate = transform(joined)
            variants.add(candidate)
            variants.add(f"  {candidate}  ")

    for variant in variants:
        assert canonicalize_topic(variant) == canonical
