"""API smoke test for startup wiring, /health, and mocked /generate."""

from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from src.api.main import app
from src.services.hypothetical_service import GenerationResponse


def test_api_health_and_generate_smoke(monkeypatch):
    monkeypatch.setattr(
        "src.api.main.hypothetical_service.health_check",
        AsyncMock(return_value={"status": "healthy", "dependencies": {}}),
    )
    monkeypatch.setattr(
        "src.api.main.llm_service.health_check",
        AsyncMock(return_value={"ollama": {"healthy": True}}),
    )
    monkeypatch.setattr(
        "src.api.main.corpus_service.health_check",
        AsyncMock(return_value={"local_corpus": True, "total_entries": 1}),
    )
    monkeypatch.setattr(
        "src.api.main.corpus_service.extract_all_topics",
        AsyncMock(return_value=["negligence"]),
    )
    monkeypatch.setattr(
        "src.api.main.hypothetical_service.generate_hypothetical",
        AsyncMock(
            return_value=GenerationResponse(
                hypothetical="Smoke hypothetical",
                analysis="Smoke analysis",
                metadata={"generation_id": 501},
                generation_time=0.5,
                validation_results={"passed": True, "quality_score": 8.0},
            )
        ),
    )

    client = TestClient(app)

    health = client.get("/health")
    assert health.status_code == 200

    generate = client.post(
        "/generate",
        json={
            "topics": ["negligence"],
            "number_parties": 2,
            "complexity_level": "basic",
        },
    )
    assert generate.status_code == 200
    assert generate.json()["metadata"]["generation_id"] == 501
