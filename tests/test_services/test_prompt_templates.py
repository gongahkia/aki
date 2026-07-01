"""Tests for prompt template topic hint normalization."""

from src.services.prompt_engineering import (
    PromptContext,
    PromptTemplateManager,
    PromptTemplateType,
)
from src.domain import (
    TOPIC_ALIASES,
    DomainPack,
    Jurisdiction,
    all_tort_topic_keys,
    canonicalize_topic,
    is_tort_topic,
    register_domain_pack,
)


def test_topic_hints_support_spaced_topic_aliases():
    manager = PromptTemplateManager()
    context = PromptContext(topics=["occupiers liability"])
    prompt = manager.format_prompt(PromptTemplateType.HYPOTHETICAL_GENERATION, context)

    assert "- occupiers_liability:" in prompt["user"]


def test_topic_hints_support_underscored_topic_keys():
    manager = PromptTemplateManager()
    context = PromptContext(topics=["occupiers_liability"])
    prompt = manager.format_prompt(PromptTemplateType.HYPOTHETICAL_GENERATION, context)

    assert "- occupiers_liability:" in prompt["user"]


def test_topic_hints_normalize_case_and_whitespace_variants():
    manager = PromptTemplateManager()
    context = PromptContext(topics=["  OcCuPiErS   LiAbIlItY  "])
    prompt = manager.format_prompt(PromptTemplateType.HYPOTHETICAL_GENERATION, context)

    assert "- occupiers_liability:" in prompt["user"]


def test_prompt_context_uses_registered_jurisdiction_label():
    register_domain_pack(
        DomainPack(
            key="prompt_tort",
            display_name="Promptland Tort Law",
            jurisdiction=Jurisdiction(key="prompt", display_name="Promptland"),
            law_domain="tort",
            canonicalize_topic=canonicalize_topic,
            is_supported_topic=is_tort_topic,
            topic_keys=all_tort_topic_keys(),
            topic_aliases=dict(TOPIC_ALIASES),
            subject_label="Tort Law",
        )
    )
    manager = PromptTemplateManager()
    context = PromptContext(
        topics=["negligence"],
        corpus_pack="prompt_tort",
        jurisdiction="prompt",
        subject="tort",
    )

    prompt = manager.format_prompt(PromptTemplateType.HYPOTHETICAL_GENERATION, context)

    assert "Promptland Tort Law" in prompt["system"]
    assert "Jurisdiction: Promptland" in prompt["user"]


def test_prompt_overlay_only_applies_to_selected_pack():
    register_domain_pack(
        DomainPack(
            key="no_overlay_tort",
            display_name="No Overlay Tort Law",
            jurisdiction=Jurisdiction(key="none", display_name="NoOverlayLand"),
            law_domain="tort",
            canonicalize_topic=canonicalize_topic,
            is_supported_topic=is_tort_topic,
            topic_keys=all_tort_topic_keys(),
            topic_aliases=dict(TOPIC_ALIASES),
            subject_label="Tort Law",
        )
    )
    manager = PromptTemplateManager()

    sg_prompt = manager.format_prompt(
        PromptTemplateType.HYPOTHETICAL_GENERATION,
        PromptContext(topics=["limitation_periods"], corpus_pack="sg_tort"),
    )
    fallback_prompt = manager.format_prompt(
        PromptTemplateType.HYPOTHETICAL_GENERATION,
        PromptContext(
            topics=["limitation_periods"],
            corpus_pack="no_overlay_tort",
            jurisdiction="none",
        ),
    )

    assert "under Singapore law" in sg_prompt["user"]
    assert "under Singapore law" not in fallback_prompt["user"]
