"""Server-rendered optional web surface for local generation workflows."""

from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from ..domain import canonicalize_topic
from ..services import GenerationRequest, corpus_service, hypothetical_service
from ..services.topic_guard import canonicalize_and_validate_topics

TEMPLATE_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

web_router = APIRouter(prefix="/web", tags=["web"])


def _base_context(
    request: Request,
    *,
    topics: List[str],
    form_data: Optional[Dict[str, Any]] = None,
    result: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "request": request,
        "topics": topics,
        "form_data": form_data
        or {
            "topic": topics[0] if topics else "",
            "provider": "ollama",
            "model": "",
            "complexity_level": "3",
            "number_parties": "3",
            "method": "pure_llm",
            "red_herrings": False,
        },
        "providers": ["ollama", "openai", "anthropic", "google", "local"],
        "methods": ["pure_llm", "ml_assisted", "hybrid"],
        "result": result,
        "error": error,
    }


async def _load_canonical_topics() -> List[str]:
    topics = await corpus_service.extract_all_topics()
    canonical = sorted({canonicalize_topic(topic) for topic in topics})
    return canonical


@web_router.get("/", response_class=HTMLResponse)
async def web_home(request: Request):
    """Render minimal web UI for local generation."""
    topics = await _load_canonical_topics()
    return templates.TemplateResponse(
        "web/index.html",
        _base_context(request, topics=topics),
    )


@web_router.post("/generate", response_class=HTMLResponse)
async def web_generate(request: Request):
    """Generate a hypothetical via server-rendered form submission."""
    topics = await _load_canonical_topics()
    form = await request.form()

    raw_topic = str(form.get("topic", "")).strip()
    provider = str(form.get("provider", "")).strip() or None
    model = str(form.get("model", "")).strip() or None
    complexity_level = str(form.get("complexity_level", "3")).strip() or "3"
    method = str(form.get("method", "pure_llm")).strip() or "pure_llm"
    red_herrings = str(form.get("red_herrings", "")).lower() in ("1", "true", "on")

    raw_parties = str(form.get("number_parties", "3")).strip() or "3"
    try:
        number_parties = max(2, min(5, int(raw_parties)))
    except ValueError:
        number_parties = 3

    form_data = {
        "topic": raw_topic,
        "provider": provider or "ollama",
        "model": model or "",
        "complexity_level": complexity_level,
        "number_parties": str(number_parties),
        "method": method,
        "red_herrings": red_herrings,
    }

    try:
        canonical_topics = canonicalize_and_validate_topics([raw_topic])
        invalid_topics = [topic for topic in canonical_topics if topic not in topics]
        if invalid_topics:
            raise ValueError(
                f"Invalid topic selection: {', '.join(invalid_topics)}"
            )

        request_model = GenerationRequest(
            topics=canonical_topics,
            number_parties=number_parties,
            complexity_level=complexity_level,
            method=method,
            provider=provider,
            model=model,
            user_preferences={"red_herrings": red_herrings},
        )
        response = await hypothetical_service.generate_hypothetical(request_model)
        result = {
            "generation_id": response.metadata.get("generation_id"),
            "hypothetical": response.hypothetical,
            "analysis": response.analysis,
            "quality_score": response.validation_results.get(
                "quality_score",
                response.validation_results.get("overall_score", 0.0),
            ),
            "validation_passed": response.validation_results.get("passed", False),
            "generation_time": response.generation_time,
        }
        return templates.TemplateResponse(
            "web/index.html",
            _base_context(
                request,
                topics=topics,
                form_data=form_data,
                result=result,
            ),
        )
    except Exception as e:
        return templates.TemplateResponse(
            "web/index.html",
            _base_context(
                request,
                topics=topics,
                form_data=form_data,
                error=f"Generation failed: {e}",
            ),
            status_code=400,
        )


__all__ = ["web_router"]
