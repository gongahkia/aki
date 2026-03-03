"""LLM provider endpoints."""

import json
from typing import Optional

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

router = APIRouter()


class LlmGenerateRequest(BaseModel):
    prompt: str
    system_prompt: Optional[str] = None
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2048, gt=0)
    model: Optional[str] = None
    correlation_id: Optional[str] = None
    timeout_seconds: Optional[int] = Field(default=None, ge=1)


class SelectProviderRequest(BaseModel):
    name: str


class SelectModelRequest(BaseModel):
    name: str


@router.get("/health")
async def llm_health(provider: Optional[str] = None):
    from ...services import llm_service
    return await llm_service.health_check(provider)


@router.get("/models")
async def llm_models(provider: Optional[str] = None):
    from ...services import llm_service
    return await llm_service.list_models(provider)


@router.post("/generate")
async def llm_generate(req: LlmGenerateRequest):
    from ...services import llm_service
    from ...services.llm_providers.base import LLMRequest
    llm_req = LLMRequest(
        prompt=req.prompt,
        system_prompt=req.system_prompt,
        temperature=req.temperature,
        max_tokens=req.max_tokens,
        model=req.model,
        correlation_id=req.correlation_id,
        timeout_seconds=req.timeout_seconds,
    )
    resp = await llm_service.generate(llm_req)
    return resp.model_dump()


@router.post("/stream")
async def llm_stream(req: LlmGenerateRequest, provider: Optional[str] = None, model: Optional[str] = None):
    from ...services import llm_service
    from ...services.llm_providers.base import LLMRequest
    llm_req = LLMRequest(
        prompt=req.prompt,
        system_prompt=req.system_prompt,
        temperature=req.temperature,
        max_tokens=req.max_tokens,
        model=req.model or model,
        stream=True,
        correlation_id=req.correlation_id,
        timeout_seconds=req.timeout_seconds,
    )

    async def event_generator():
        try:
            async for chunk in llm_service.stream_generate(llm_req, provider=provider, model=model):
                yield f"event: token\ndata: {json.dumps({'text': chunk})}\n\n"
            yield f"event: done\ndata: {json.dumps({'finish_reason': 'stop'})}\n\n"
        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'code': 'stream_error', 'message': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/select-provider")
async def select_provider(req: SelectProviderRequest):
    from ...services import llm_service
    llm_service.select_provider(req.name)
    return {"selected": req.name}


@router.post("/select-model")
async def select_model(req: SelectModelRequest):
    from ...services import llm_service
    llm_service.select_model(req.name)
    return {"selected": req.name}


@router.get("/session-cost")
async def session_cost():
    from ...services import llm_service
    return llm_service.get_session_cost()
