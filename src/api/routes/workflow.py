"""Workflow facade endpoints for generation and regeneration."""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()


class GenerateRequest(BaseModel):
    topics: List[str] = Field(min_length=1, max_length=10)
    law_domain: str = "tort"
    number_parties: int = Field(default=3, ge=2, le=5)
    complexity_level: str = "intermediate"
    sample_size: int = Field(default=3, ge=1, le=10)
    user_preferences: Optional[Dict[str, Any]] = None
    method: str = "pure_llm"
    provider: Optional[str] = None
    model: Optional[str] = None
    include_analysis: bool = True
    correlation_id: Optional[str] = None


class RegenerateRequest(BaseModel):
    generation_id: int
    correlation_id: Optional[str] = None
    fallback_request: Optional[Dict[str, Any]] = None


class ReportRequest(BaseModel):
    generation_id: int
    issue_types: List[str] = Field(default_factory=list)
    comment: Optional[str] = None
    correlation_id: Optional[str] = None
    is_locked: bool = True


@router.post("/generate")
async def generate(req: GenerateRequest):
    from ...services import workflow_facade
    from ...services.hypothetical_service import GenerationRequest
    gen_req = GenerationRequest(
        topics=req.topics,
        law_domain=req.law_domain,
        number_parties=req.number_parties,
        complexity_level=req.complexity_level,
        sample_size=req.sample_size,
        user_preferences=req.user_preferences,
        method=req.method,
        provider=req.provider,
        model=req.model,
        include_analysis=req.include_analysis,
        correlation_id=req.correlation_id,
    )
    try:
        result = await workflow_facade.generate_generation(gen_req, correlation_id=req.correlation_id)
        return {
            "hypothetical": result.response.hypothetical,
            "analysis": result.response.analysis,
            "generation_time": result.response.generation_time,
            "validation_results": result.response.validation_results,
            "metadata": result.response.metadata,
        }
    except Exception as e:
        from ...services.error_mapper import map_exception
        err = map_exception(e)
        raise HTTPException(status_code=err.http_status, detail={
            "code": err.code, "message": err.message, "hint": err.hint, "retryable": err.retryable,
        })


@router.post("/regenerate")
async def regenerate(req: RegenerateRequest):
    from ...services import workflow_facade
    try:
        result = await workflow_facade.regenerate_generation(
            generation_id=req.generation_id,
            correlation_id=req.correlation_id,
            fallback_request=req.fallback_request,
        )
        return {
            "source_generation_id": result.source_generation_id,
            "feedback_context": result.feedback_context,
            "request_data": result.request_data,
            "regenerated": {
                "hypothetical": result.regenerated.hypothetical,
                "analysis": result.regenerated.analysis,
                "generation_time": result.regenerated.generation_time,
                "validation_results": result.regenerated.validation_results,
                "metadata": result.regenerated.metadata,
            },
        }
    except Exception as e:
        from ...services.error_mapper import map_exception
        err = map_exception(e)
        raise HTTPException(status_code=err.http_status, detail={
            "code": err.code, "message": err.message, "hint": err.hint, "retryable": err.retryable,
        })


@router.post("/report")
async def save_report(req: ReportRequest):
    from ...services import workflow_facade
    report_id = await workflow_facade.save_generation_report(
        generation_id=req.generation_id,
        issue_types=req.issue_types,
        comment=req.comment,
        correlation_id=req.correlation_id,
        is_locked=req.is_locked,
    )
    return {"report_id": report_id}


@router.get("/reports/{generation_id}")
async def list_reports(generation_id: int):
    from ...services import workflow_facade
    reports = await workflow_facade.list_generation_reports(generation_id)
    return {"reports": [r.model_dump() if hasattr(r, 'model_dump') else r.__dict__ for r in reports]}
