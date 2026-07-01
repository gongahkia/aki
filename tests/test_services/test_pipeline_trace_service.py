import pytest

from src.services.pipeline_trace_service import (
    default_pipeline_trace_request,
    pipeline_trace_service,
)


@pytest.mark.asyncio
async def test_pipeline_trace_contains_required_stages_and_redacts_prompt():
    trace = await pipeline_trace_service.build_trace(default_pipeline_trace_request())

    stage_ids = [stage["id"] for stage in trace["stages"]]
    assert stage_ids == [
        "input",
        "classification",
        "scoring",
        "planning",
        "retrieval",
        "prompt",
        "generation",
        "validation",
        "study",
    ]
    prompt_stage = next(stage for stage in trace["stages"] if stage["id"] == "prompt")
    assert prompt_stage["details"]["redacted"] is True
    assert "user_prompt" not in prompt_stage["details"]
    study_stage = next(stage for stage in trace["stages"] if stage["id"] == "study")
    assert "anki_tsv_preview" in study_stage["details"]
    assert trace["summary"]["passed"] is True


@pytest.mark.asyncio
async def test_pipeline_trace_can_expose_prompt_when_requested():
    trace = await pipeline_trace_service.build_trace(
        default_pipeline_trace_request(), expose_prompt=True
    )

    prompt_stage = next(stage for stage in trace["stages"] if stage["id"] == "prompt")
    assert prompt_stage["details"]["redacted"] is False
    assert "user_prompt" in prompt_stage["details"]
    assert "Target Topics" in prompt_stage["details"]["user_prompt"]


@pytest.mark.asyncio
async def test_pipeline_trace_explains_validation_failures():
    request = default_pipeline_trace_request().model_copy(
        update={"topics": ["battery"]}
    )
    trace = await pipeline_trace_service.build_trace(request)

    validation_stage = next(
        stage for stage in trace["stages"] if stage["id"] == "validation"
    )
    assert validation_stage["status"] == "warning"
    assert validation_stage["details"]["failure_reasons"]
    assert trace["summary"]["failure_reasons"]
