"""Demo route surfaces for practice and pipeline trace pages."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field

from ..frontend import demo_page_path
from ...services.hypothetical_service import GenerationRequest
from ...services.pipeline_trace_service import (
    default_pipeline_trace_request,
    pipeline_trace_service,
)

router = APIRouter()


class PipelineTraceRequest(BaseModel):
    topics: List[str] = Field(default_factory=lambda: ["negligence", "causation"])
    corpus_pack: str = "sg_tort"
    jurisdiction: str = "sg"
    subject: str = "tort"
    subtopics: List[str] = Field(default_factory=list)
    law_domain: str = "tort"
    number_parties: int = Field(default=3, ge=2, le=5)
    complexity_level: str = "intermediate"
    sample_size: int = Field(default=3, ge=1, le=10)
    user_preferences: Optional[Dict[str, Any]] = None
    live: bool = False
    expose_prompt: bool = False
    expose_provider: bool = False


def _topics_from_query(raw_topics: str) -> List[str]:
    return [topic.strip() for topic in raw_topics.split(",") if topic.strip()]


@router.get("/pipeline", response_class=HTMLResponse)
async def pipeline_page() -> RedirectResponse:
    return RedirectResponse(url="/demo", status_code=307)


@router.get("", response_class=HTMLResponse)
async def generation_page() -> FileResponse:
    return FileResponse(demo_page_path("index.html"))


@router.get("/generate", response_class=HTMLResponse)
async def generation_page_alias() -> FileResponse:
    return FileResponse(demo_page_path("index.html"))


@router.get("/pipeline/trace")
async def pipeline_trace(
    topics: str = Query(default="negligence, causation"),
    corpus_pack: str = "sg_tort",
    jurisdiction: str = "sg",
    subject: str = "tort",
    live: bool = False,
    expose_prompt: bool = False,
    expose_provider: bool = False,
):
    request = default_pipeline_trace_request().model_copy(
        update={
            "topics": _topics_from_query(topics),
            "corpus_pack": corpus_pack,
            "jurisdiction": jurisdiction,
            "subject": subject,
            "law_domain": subject,
        }
    )
    request = GenerationRequest(**request.model_dump())
    return await pipeline_trace_service.build_trace(
        request,
        live=live,
        expose_prompt=expose_prompt,
        expose_provider=expose_provider,
    )


@router.post("/pipeline/trace")
async def pipeline_trace_post(req: PipelineTraceRequest):
    request = GenerationRequest(
        topics=req.topics,
        corpus_pack=req.corpus_pack,
        jurisdiction=req.jurisdiction,
        subject=req.subject,
        subtopics=req.subtopics,
        law_domain=req.law_domain,
        number_parties=req.number_parties,
        complexity_level=req.complexity_level,
        sample_size=req.sample_size,
        user_preferences=req.user_preferences,
    )
    return await pipeline_trace_service.build_trace(
        request,
        live=req.live,
        expose_prompt=req.expose_prompt,
        expose_provider=req.expose_provider,
    )
