"""Tests for shared API/TUI workflow facade."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.services.hypothetical_service import GenerationRequest, GenerationResponse
from src.services.workflow_facade import WorkflowFacade, WorkflowFacadeError


@pytest.mark.asyncio
async def test_generate_generation_validates_topics_and_calls_hypothetical_service():
    corpus = SimpleNamespace(extract_all_topics=AsyncMock(return_value=["negligence"]))
    expected_response = GenerationResponse(
        hypothetical="Generated negligence scenario",
        analysis="Analysis",
        metadata={"generation_id": 1},
        generation_time=0.2,
        validation_results={"passed": True, "quality_score": 8.0},
    )
    hypothetical = SimpleNamespace(
        generate_hypothetical=AsyncMock(return_value=expected_response)
    )
    database = SimpleNamespace()
    facade = WorkflowFacade(
        corpus_service=corpus,
        hypothetical_service=hypothetical,
        database_service=database,
    )

    request = GenerationRequest(topics=["Negligence"], include_analysis=True)
    result = await facade.generate_generation(request, correlation_id="corr-1")

    assert result.request.topics == ["negligence"]
    assert result.request.correlation_id == "corr-1"
    assert result.response.metadata["generation_id"] == 1
    hypothetical.generate_hypothetical.assert_awaited_once()


@pytest.mark.asyncio
async def test_save_generation_report_translates_foreign_key_error():
    database = SimpleNamespace(
        save_generation_report=AsyncMock(
            side_effect=RuntimeError("FOREIGN KEY constraint failed")
        )
    )
    facade = WorkflowFacade(
        corpus_service=SimpleNamespace(),
        hypothetical_service=SimpleNamespace(),
        database_service=database,
    )

    with pytest.raises(WorkflowFacadeError) as exc_info:
        await facade.save_generation_report(
            generation_id=999,
            issue_types=["missing_topic"],
            comment="bad output",
        )

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_regenerate_generation_reuses_feedback_context_and_lineage():
    captured = {}

    async def _generate(req):
        captured["request"] = req
        return GenerationResponse(
            hypothetical="Regenerated scenario",
            analysis="Updated analysis",
            metadata={"generation_id": 55},
            generation_time=0.3,
            validation_results={"passed": True, "quality_score": 8.3},
        )

    db = SimpleNamespace(
        get_generation_by_id=AsyncMock(
            return_value={
                "request": {
                    "topics": ["negligence"],
                    "law_domain": "tort",
                    "number_parties": 3,
                    "complexity_level": "intermediate",
                    "sample_size": 3,
                    "user_preferences": {"feedback": "prior note"},
                    "method": "pure_llm",
                    "provider": "ollama",
                    "model": "llama3",
                    "include_analysis": True,
                    "retry_attempt": 1,
                },
                "retry_attempt": 1,
            }
        ),
        build_regeneration_feedback_context=AsyncMock(return_value="new issues"),
        get_generation_reports=AsyncMock(
            return_value=[SimpleNamespace(issue_types=["missing_topic"], comment=None)]
        ),
    )
    facade = WorkflowFacade(
        corpus_service=SimpleNamespace(),
        hypothetical_service=SimpleNamespace(
            generate_hypothetical=AsyncMock(side_effect=_generate)
        ),
        database_service=db,
    )

    result = await facade.regenerate_generation(
        generation_id=10,
        correlation_id="regen-corr",
    )

    request = captured["request"]
    assert request.parent_generation_id == 10
    assert request.retry_attempt == 2
    assert request.retry_reason.startswith("report_feedback")
    assert "new issues" in request.user_preferences["feedback"]
    assert result.regenerated.metadata["generation_id"] == 55


@pytest.mark.asyncio
async def test_regenerate_generation_appends_quality_gate_failures_to_feedback():
    captured = {}

    async def _generate(req):
        captured["request"] = req
        return GenerationResponse(
            hypothetical="Regenerated scenario",
            analysis="Updated analysis",
            metadata={"generation_id": 88},
            generation_time=0.2,
            validation_results={"passed": True, "quality_score": 8.0},
        )

    db = SimpleNamespace(
        get_generation_by_id=AsyncMock(
            return_value={
                "request": {
                    "topics": ["negligence"],
                    "law_domain": "tort",
                    "number_parties": 3,
                    "complexity_level": "intermediate",
                    "sample_size": 3,
                    "user_preferences": {"feedback": "prior note"},
                    "method": "pure_llm",
                    "provider": "ollama",
                    "model": "llama3",
                    "include_analysis": True,
                    "retry_attempt": 0,
                },
                "response": {
                    "validation_results": {
                        "adherence_check": {
                            "quality_gate": {"failed_checks": ["legal_realism"]}
                        }
                    }
                },
                "retry_attempt": 0,
            }
        ),
        build_regeneration_feedback_context=AsyncMock(return_value="report context"),
        get_generation_reports=AsyncMock(return_value=[]),
    )
    facade = WorkflowFacade(
        corpus_service=SimpleNamespace(),
        hypothetical_service=SimpleNamespace(
            generate_hypothetical=AsyncMock(side_effect=_generate)
        ),
        database_service=db,
    )

    await facade.regenerate_generation(generation_id=20, correlation_id="regen-corr")

    feedback = captured["request"].user_preferences["feedback"]
    assert "prior note" in feedback
    assert "report context" in feedback
    assert "Validation failures:" in feedback
    assert "legal realism score below threshold" in feedback


@pytest.mark.asyncio
async def test_regenerate_generation_uses_quality_gate_reasons_when_report_context_empty():
    captured = {}

    async def _generate(req):
        captured["request"] = req
        return GenerationResponse(
            hypothetical="Regenerated scenario",
            analysis="Updated analysis",
            metadata={"generation_id": 99},
            generation_time=0.2,
            validation_results={"passed": True, "quality_score": 8.2},
        )

    db = SimpleNamespace(
        get_generation_by_id=AsyncMock(
            return_value={
                "request": {
                    "topics": ["negligence"],
                    "law_domain": "tort",
                    "number_parties": 2,
                    "complexity_level": "intermediate",
                    "sample_size": 3,
                    "user_preferences": {},
                    "method": "pure_llm",
                    "provider": "ollama",
                    "model": "llama3",
                    "include_analysis": True,
                    "retry_attempt": 0,
                },
                "response": {
                    "validation_results": {
                        "adherence_check": {
                            "quality_gate": {"failed_checks": ["quality_score"]},
                            "checks": {"party_count": {"passed": False}},
                        },
                        "similarity_check": {"passed": False},
                    }
                },
                "retry_attempt": 0,
            }
        ),
        build_regeneration_feedback_context=AsyncMock(return_value=""),
        get_generation_reports=AsyncMock(return_value=[]),
    )
    facade = WorkflowFacade(
        corpus_service=SimpleNamespace(),
        hypothetical_service=SimpleNamespace(
            generate_hypothetical=AsyncMock(side_effect=_generate)
        ),
        database_service=db,
    )

    await facade.regenerate_generation(generation_id=21, correlation_id="regen-corr")

    feedback = captured["request"].user_preferences["feedback"]
    assert feedback.startswith("Validation failures:")
    assert "overall quality score below threshold" in feedback
    assert "similarity check failed" in feedback
    assert "party_count validation failed" in feedback
