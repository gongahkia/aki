"""Heuristic preview estimator for generation token, latency, and cost metadata."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel

from ..config import settings
from .hypothetical_service import GenerationRequest


class GeneratePreviewResponse(BaseModel):
    topics: List[str]
    provider: Optional[str] = None
    model: Optional[str] = None
    estimated_input_tokens: int
    estimated_output_tokens: int
    estimated_total_tokens: int
    estimated_latency_seconds: float
    estimated_cost_usd: float
    confidence: str = "heuristic"


def estimate_generation_preview(request: GenerationRequest) -> GeneratePreviewResponse:
    """Estimate generation cost/latency without executing generation."""
    complexity_map = {
        "beginner": 2,
        "basic": 2,
        "intermediate": 3,
        "advanced": 4,
        "expert": 5,
    }
    raw_complexity = str(request.complexity_level).strip().lower()
    if raw_complexity.isdigit():
        complexity_factor = max(1, min(5, int(raw_complexity)))
    else:
        complexity_factor = complexity_map.get(raw_complexity, 3)

    topic_count = max(1, len(request.topics))
    sample_size = max(1, int(request.sample_size))
    party_count = max(2, int(request.number_parties))

    estimated_input_tokens = (
        650
        + (topic_count * 90)
        + (sample_size * 220)
        + (party_count * 55)
        + (complexity_factor * 120)
    )
    estimated_output_tokens = (
        700
        + (complexity_factor * 260)
        + (party_count * 80)
        + (120 if request.method in ("hybrid", "ml_assisted") else 0)
    )
    total_tokens = estimated_input_tokens + estimated_output_tokens

    provider = (request.provider or settings.llm.provider or "ollama").lower()
    provider_latency_factor = {
        "openai": 1.0,
        "anthropic": 1.1,
        "google": 0.9,
        "ollama": 1.8,
        "local": 1.7,
    }.get(provider, 1.2)
    estimated_latency_seconds = round(
        1.2 + (total_tokens / 900.0) * provider_latency_factor, 2
    )

    # Rough blended token pricing by provider (USD per 1k tokens).
    provider_rate_per_1k = {
        "openai": 0.005,
        "anthropic": 0.006,
        "google": 0.003,
        "ollama": 0.0,
        "local": 0.0,
    }.get(provider, 0.004)
    estimated_cost_usd = round((total_tokens / 1000.0) * provider_rate_per_1k, 6)

    return GeneratePreviewResponse(
        topics=request.topics,
        provider=request.provider,
        model=request.model,
        estimated_input_tokens=estimated_input_tokens,
        estimated_output_tokens=estimated_output_tokens,
        estimated_total_tokens=total_tokens,
        estimated_latency_seconds=estimated_latency_seconds,
        estimated_cost_usd=estimated_cost_usd,
    )
