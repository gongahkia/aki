"""Tests for self-refine loop orchestration."""

import json
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest

from src.config import settings
from src.services.hypothetical_service import (
    GenerationRequest,
    HypotheticalService,
    ValidationResult,
)
from src.services.prompt_engineering import PromptContext, format_revise_prompt
from src.services.prompt_engineering.schemas import RefineCritique
from src.services.refine_loop import RefineLoop


@pytest.mark.asyncio
async def test_refine_loop_revises_until_non_blocking_and_writes_trace(tmp_path):
    generated: list[str] = []

    async def generate(prompt: str) -> str:
        generated.append(prompt)
        return "fixed draft with enough legal detail"

    async def validate(text: str) -> dict[str, Any]:
        if text.startswith("bad"):
            return {"passed": False, "missing_topics": ["negligence"]}
        return {"passed": True, "missing_topics": []}

    trace_path = tmp_path / "trace.jsonl"
    loop = RefineLoop(
        generate=generate,
        rule_based_validate=validate,
        max_iterations=2,
        trace_path=trace_path,
    )

    result = await loop.run(
        "bad draft", lambda draft, critique: f"revise {draft} {critique.missing_topics}"
    )

    assert result.hypothetical.startswith("fixed")
    assert result.iterations == 1
    assert result.final_critique.is_blocking() is False
    assert len(generated) == 1
    assert len(trace_path.read_text(encoding="utf-8").splitlines()) == 2


@pytest.mark.asyncio
async def test_refine_loop_stops_at_max_iterations_with_blocking_critique(tmp_path):
    calls = 0

    async def generate(prompt: str) -> str:
        nonlocal calls
        calls += 1
        return "still missing topic"

    async def validate(text: str) -> dict[str, Any]:
        return {"passed": False, "missing_topics": ["duty_of_care"]}

    loop = RefineLoop(
        generate=generate,
        rule_based_validate=validate,
        max_iterations=1,
        trace_path=tmp_path / "blocked.jsonl",
    )

    result = await loop.run("bad draft", lambda draft, critique: "revise")

    assert calls == 1
    assert result.iterations == 1
    assert result.final_critique.is_blocking() is True


def test_format_revise_prompt_includes_critique_feedback():
    critique = RefineCritique(
        iteration=0,
        missing_topics=["duty_of_care"],
        ml_gate={
            "passed": False,
            "per_topic": {"duty_of_care": 0.1},
            "threshold": 0.4,
        },
        rule_based={"passed": False},
    )

    prompt = format_revise_prompt(
        PromptContext(topics=["duty_of_care"]),
        "Prior draft text",
        critique,
    )

    assert "Prior draft text" in prompt
    assert "duty_of_care" in prompt
    assert "Produce a revised hypothetical" in prompt


@pytest.mark.asyncio
async def test_generate_hypothetical_runs_refine_loop_and_attaches_metadata(
    monkeypatch, tmp_path
):
    service = HypotheticalService()
    service_any = cast(Any, service)
    service_any._get_relevant_context = AsyncMock(return_value=[])
    service_any._generate_hypothetical_draft = AsyncMock(
        return_value=("bad draft with enough words to enter refine loop", {})
    )
    service_any._ml_post_process = AsyncMock(side_effect=lambda request, text: text)
    service_any._generate_hypothetical_text_from_prompt = AsyncMock(
        return_value="fixed draft with enough legal detail for final response"
    )
    service_any._rule_based_validate_dict = AsyncMock(
        side_effect=[
            {"passed": False, "missing_topics": ["negligence"]},
            {"passed": True, "missing_topics": []},
        ]
    )
    service_any._validate_hypothetical = AsyncMock(
        return_value=ValidationResult(
            adherence_check={"passed": True},
            similarity_check={"passed": True},
            quality_score=8.0,
            passed=True,
        )
    )
    service_any._generate_legal_analysis = AsyncMock(return_value="")
    database_service_any = cast(Any, service.database_service)
    database_service_any.save_generation = AsyncMock(return_value=201)
    monkeypatch.setattr(settings, "refine_trace_dir", str(tmp_path))
    monkeypatch.setattr(settings, "refine_max_iterations", 1)
    monkeypatch.setattr(settings, "ml_gate_blocking", False)
    monkeypatch.setattr(settings, "nli_verifier_enabled", False)

    response = await service.generate_hypothetical(
        GenerationRequest(
            topics=["negligence"],
            include_analysis=False,
            user_preferences={"disable_cache": True},
        )
    )

    assert response.hypothetical.startswith("fixed")
    assert response.metadata["refine"]["iterations"] == 1
    trace_path = tmp_path / f"{response.metadata['correlation_id']}.jsonl"
    rows = [json.loads(line) for line in trace_path.read_text().splitlines()]
    assert [row["iteration"] for row in rows] == [0, 1]
