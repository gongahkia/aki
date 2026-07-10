from typing import Any, cast
from unittest.mock import AsyncMock

import pytest

from src.services.export_service import format_practice_artifact
from src.services.hypothetical_service import (
    GenerationRequest,
    HypotheticalService,
    ValidationResult,
)


def test_progressive_hints_artifact_includes_checklist_rubric_and_hints():
    request = GenerationRequest(
        topics=["negligence", "causation"],
        practice_mode="progressive_hints",
    )
    artifact = HypotheticalService._build_practice_artifact(
        request=request,
        hypothetical="A Singapore tort fact pattern.",
        validation_results=ValidationResult(passed=True, quality_score=8.0),
        model_answer="Model answer text.",
    )

    assert artifact["mode"] == "progressive_hints"
    assert artifact["answer_visibility"] == "hidden_until_attempt"
    assert [item["topic"] for item in artifact["issue_checklist"]] == [
        "negligence",
        "causation",
    ]
    assert sum(item["points"] for item in artifact["rubric"]) == 100
    assert [hint["level"] for hint in artifact["hints"]] == [1, 2, 3]
    assert "model_answer" in artifact["post_attempt_reveal"]["includes"]


def test_timed_exam_artifact_clamps_timer_preference():
    request = GenerationRequest(
        topics=["negligence"],
        practice_mode="timed_exam",
        user_preferences={"timer_seconds": 60},
    )
    artifact = HypotheticalService._build_practice_artifact(
        request=request,
        hypothetical="A Singapore tort fact pattern.",
        validation_results=ValidationResult(passed=True),
        model_answer="",
    )

    assert artifact["timer"]["seconds"] == 300


def test_export_practice_artifact_text_includes_mode_checklist_and_rubric():
    practice = {
        "mode": "issue_spotting",
        "answer_visibility": "hidden_until_attempt",
        "issue_checklist": [
            {"label": "Negligence", "student_task": "Identify negligence."}
        ],
        "rubric": [
            {
                "criterion": "issue_spotting",
                "points": 30,
                "description": "spots issues",
            }
        ],
    }

    lines = format_practice_artifact(practice)

    assert "Practice mode: issue_spotting" in lines
    assert any("Negligence" in line for line in lines)
    assert any("issue_spotting" in line for line in lines)


@pytest.mark.asyncio
async def test_model_answer_review_mode_generates_model_answer_without_preference():
    service = HypotheticalService()
    service_any = cast(Any, service)
    service_any._get_relevant_context = AsyncMock(return_value=[])
    service_any._generate_hypothetical_text = AsyncMock(return_value="Fact pattern.")
    service_any._validate_hypothetical = AsyncMock(
        return_value=ValidationResult(passed=True, quality_score=8.0)
    )
    service_any._generate_legal_analysis = AsyncMock(return_value="")
    service_any._generate_model_answer = AsyncMock(return_value="Review answer.")
    database_service_any = cast(Any, service.database_service)
    database_service_any.save_generation = AsyncMock(return_value=7)

    response = await service.generate_hypothetical(
        GenerationRequest(
            topics=["negligence"],
            include_analysis=False,
            practice_mode="model_answer_review",
        )
    )

    assert response.model_answer == "Review answer."
    assert response.metadata["practice"]["mode"] == "model_answer_review"
    assert response.validation_results["answer_quality"]["passed"] is False
    assert (
        response.validation_results["answer_quality"]["checks"]["irac_structure"][
            "passed"
        ]
        is False
    )
    service_any._generate_model_answer.assert_awaited_once()
