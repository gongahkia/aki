"""Tests for local response cache in HypotheticalService."""

from typing import Any, cast
from unittest.mock import AsyncMock

import pytest

from src.services.hypothetical_service import (
    GenerationRequest,
    GenerationResponse,
    HypotheticalService,
    ValidationResult,
)


@pytest.mark.asyncio
async def test_response_cache_round_trip():
    service = HypotheticalService()
    service._response_cache_enabled = True
    service._response_cache_ttl_seconds = 60

    request = GenerationRequest(topics=["negligence"])
    response = GenerationResponse(
        hypothetical="Cached hypothetical text",
        analysis="Cached analysis text",
        metadata={"generation_id": 42},
        generation_time=0.2,
        validation_results={"passed": True, "quality_score": 8.5},
    )

    await service._cache_response(request, response)
    cached = await service._get_cached_response(request)

    assert cached is not None
    assert cached.hypothetical == response.hypothetical
    assert cached.metadata["generation_id"] == 42


@pytest.mark.asyncio
async def test_generate_hypothetical_uses_cached_response():
    service = HypotheticalService()
    service._response_cache_enabled = True
    service._response_cache_ttl_seconds = 60
    service_any = cast(Any, service)

    service_any._get_relevant_context = AsyncMock(return_value=[])
    service_any._generate_hypothetical_text = AsyncMock(
        return_value="A negligence hypothetical with sufficient length for testing."
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
    database_service_any.save_generation = AsyncMock(return_value=101)

    request = GenerationRequest(
        topics=["negligence"],
        include_analysis=False,
        user_preferences={"prioritize_latency": True},
    )

    first = await service.generate_hypothetical(request)
    second = await service.generate_hypothetical(
        request.model_copy(update={"correlation_id": "cache-test-2"})
    )

    assert first.metadata["cache_hit"] is False
    assert second.metadata["cache_hit"] is True
    assert second.hypothetical == first.hypothetical
    assert service_any._get_relevant_context.await_count == 1


@pytest.mark.asyncio
async def test_seeded_requests_reuse_cache_for_identical_seed():
    service = HypotheticalService()
    service._response_cache_enabled = True
    service._response_cache_ttl_seconds = 60
    service_any = cast(Any, service)

    service_any._get_relevant_context = AsyncMock(return_value=[])
    service_any._generate_hypothetical_text = AsyncMock(
        return_value="Seeded deterministic hypothetical output for cache test."
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
    database_service_any.save_generation = AsyncMock(return_value=102)

    request = GenerationRequest(
        topics=["negligence"],
        include_analysis=False,
        user_preferences={"seed": 424242, "prioritize_latency": True},
    )

    first = await service.generate_hypothetical(request)
    second = await service.generate_hypothetical(
        request.model_copy(update={"correlation_id": "seed-cache-hit"})
    )

    assert first.metadata["deterministic_seed"] == 424242
    assert second.metadata["cache_hit"] is True
    assert service_any._generate_hypothetical_text.await_count == 1


@pytest.mark.asyncio
async def test_seeded_requests_do_not_share_cache_across_different_seeds():
    service = HypotheticalService()
    service._response_cache_enabled = True
    service._response_cache_ttl_seconds = 60
    service_any = cast(Any, service)

    service_any._get_relevant_context = AsyncMock(return_value=[])
    service_any._generate_hypothetical_text = AsyncMock(
        side_effect=[
            "Seed 111 output for regression test.",
            "Seed 222 output for regression test.",
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
    database_service_any.save_generation = AsyncMock(return_value=103)

    request_a = GenerationRequest(
        topics=["negligence"],
        include_analysis=False,
        user_preferences={"seed": 111, "prioritize_latency": True},
    )
    request_b = GenerationRequest(
        topics=["negligence"],
        include_analysis=False,
        user_preferences={"seed": 222, "prioritize_latency": True},
    )

    first = await service.generate_hypothetical(request_a)
    second = await service.generate_hypothetical(request_b)

    assert first.metadata["cache_hit"] is False
    assert second.metadata["cache_hit"] is False
    assert service_any._generate_hypothetical_text.await_count == 2
