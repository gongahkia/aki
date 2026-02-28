"""Tests for prompt template topic hint normalization."""

from src.services.prompt_engineering import (
    PromptContext,
    PromptTemplateManager,
    PromptTemplateType,
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
