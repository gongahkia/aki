"""Contract tests for /generate/preview and /generate payload consistency."""

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.services import GenerationExecutionResult
from src.services.hypothetical_service import GenerationRequest, GenerationResponse


@pytest.fixture
def generation_request_payload():
    return {
        "topics": ["negligence"],
        "law_domain": "tort",
        "number_parties": 3,
        "complexity_level": "intermediate",
        "sample_size": 3,
        "method": "pure_llm",
        "provider": "ollama",
        "model": "llama3",
        "include_analysis": True,
    }


def test_preview_and_generate_contract_consistency(monkeypatch, generation_request_payload):
    client = TestClient(app, base_url="http://localhost")

    monkeypatch.setattr(
        "src.api.main.corpus_service.extract_all_topics",
        AsyncMock(return_value=["negligence", "duty_of_care"]),
    )

    async def _fake_generate_generation(request, correlation_id=None):
        normalized = request.model_copy(update={"topics": ["negligence"]})
        response = GenerationResponse(
            hypothetical="Contract test hypothetical",
            analysis="Contract test analysis",
            metadata={"topics": ["negligence"], "provider": request.provider},
            generation_time=0.4,
            validation_results={"passed": True, "quality_score": 8.0},
        )
        return GenerationExecutionResult(request=normalized, response=response)

    monkeypatch.setattr(
        "src.api.main.workflow_facade.generate_generation",
        _fake_generate_generation,
    )

    preview = client.post("/generate/preview", json=generation_request_payload)
    assert preview.status_code == 200
    preview_payload = preview.json()
    assert preview_payload["topics"] == ["negligence"]
    assert preview_payload["estimated_total_tokens"] > 0
    assert preview_payload["estimated_latency_seconds"] > 0

    generate = client.post("/generate", json=generation_request_payload)
    assert generate.status_code == 200
    generate_payload = generate.json()
    assert generate_payload["metadata"]["topics"] == ["negligence"]
    assert generate_payload["metadata"]["provider"] == generation_request_payload["provider"]
