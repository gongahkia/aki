"""Tests for structured generation adapter and service fallback."""

from typing import Any, cast
from unittest.mock import AsyncMock

import pytest

from src.services.hypothetical_service import GenerationRequest, HypotheticalService
from src.services.prompt_engineering import PromptContext, format_structured_prompt
from src.services.prompt_engineering.schemas import HypotheticalDraft
from src.services.prompt_engineering.structured import generate_structured


def _draft(text: str | None = None) -> HypotheticalDraft:
    narrative = (
        "In Singapore, a delivery rider collided with a pedestrian after a "
        "building manager ignored repeated warnings about a defective loading bay "
        "barrier and redirected traffic through a crowded walkway."
    )
    return HypotheticalDraft(
        corpus_pack="sg_tort",
        jurisdiction="sg",
        subject="tort",
        requested_topics=["negligence"],
        facts={
            "setting": "Singapore office tower",
            "narrative": narrative,
            "key_events": ["warning ignored", "collision occurred"],
        },
        parties=[
            {"name": "Tan", "role": "claimant"},
            {"name": "Bright Services", "role": "defendant"},
            {"name": "Lim", "role": "witness"},
        ],
        issues=[
            {
                "topic": "negligence",
                "question": "Whether Bright Services breached its duty of care.",
            }
        ],
        text=text or narrative,
    )


class StructuredProvider:
    supports_json_schema = True

    async def generate_structured(
        self, schema: type[HypotheticalDraft], prompt: str, **kwargs: Any
    ) -> HypotheticalDraft:
        return _draft()


class TextOnlyProvider:
    supports_json_schema = False

    async def generate_structured(
        self, schema: type[HypotheticalDraft], prompt: str, **kwargs: Any
    ) -> HypotheticalDraft:
        raise AssertionError("should not be called")


@pytest.mark.asyncio
async def test_generate_structured_adapter_validates_provider_result():
    result = await generate_structured(
        StructuredProvider(), HypotheticalDraft, "Generate JSON"
    )

    assert isinstance(result, HypotheticalDraft)
    assert result.facts.narrative.startswith("In Singapore")


@pytest.mark.asyncio
async def test_generate_structured_adapter_rejects_unsupported_provider():
    with pytest.raises(NotImplementedError):
        await generate_structured(
            TextOnlyProvider(), HypotheticalDraft, "Generate JSON"
        )


@pytest.mark.asyncio
async def test_structured_validation_error_falls_back_to_text_path():
    service = HypotheticalService()
    service_any = cast(Any, service)
    service.llm_service = AsyncMock()
    service.llm_service.generate_structured = AsyncMock(return_value={"text": "bad"})
    service_any._generate_hypothetical_text = AsyncMock(
        return_value="Fallback hypothetical with enough length to pass the guard."
    )

    request = GenerationRequest(topics=["negligence"], include_analysis=False)
    hypothetical, extras = await service._generate_hypothetical_draft(request, [])

    assert hypothetical.startswith("Fallback hypothetical")
    assert extras == {}
    service_any._generate_hypothetical_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_unsupported_structured_provider_falls_back_to_text_path():
    service = HypotheticalService()
    service_any = cast(Any, service)
    service.llm_service = AsyncMock()
    service.llm_service.generate_structured = AsyncMock(
        side_effect=NotImplementedError("unsupported")
    )
    service_any._generate_hypothetical_text = AsyncMock(
        return_value="Text-only fallback hypothetical with sufficient length."
    )

    request = GenerationRequest(topics=["negligence"], include_analysis=False)
    hypothetical, extras = await service._generate_hypothetical_draft(request, [])

    assert hypothetical.startswith("Text-only fallback")
    assert extras == {}
    service_any._generate_hypothetical_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_structured_draft_attaches_metadata():
    service = HypotheticalService()
    service.llm_service = AsyncMock()
    service.llm_service.generate_structured = AsyncMock(return_value=_draft())

    request = GenerationRequest(topics=["negligence"], include_analysis=False)
    hypothetical, extras = await service._generate_hypothetical_draft(request, [])

    assert hypothetical == _draft().text
    assert extras["structured_draft"]["facts"]["setting"] == "Singapore office tower"


def test_format_structured_prompt_includes_schema_directive():
    prompt = format_structured_prompt(
        PromptContext(topics=["negligence"]), "HypotheticalDraft"
    )

    assert "You MUST return valid JSON matching the schema below." in prompt
    assert '"HypotheticalDraft"' in prompt
