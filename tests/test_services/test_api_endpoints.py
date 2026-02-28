"""Regression coverage for generation/report/regenerate API endpoints."""

from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from src.api.main import app
from src.services.database_service import GenerationReport
from src.services.hypothetical_service import GenerationResponse


def _mock_generation_response(generation_id: int = 101) -> GenerationResponse:
    return GenerationResponse(
        hypothetical="Generated hypothetical text",
        analysis="Generated legal analysis",
        metadata={"generation_id": generation_id},
        generation_time=1.25,
        validation_results={"passed": True, "quality_score": 8.2},
    )


def test_generate_endpoint_accepts_provider_and_model(monkeypatch):
    client = TestClient(app)

    monkeypatch.setattr(
        "src.api.main.corpus_service.extract_all_topics",
        AsyncMock(return_value=["negligence", "duty_of_care"]),
    )

    async def _fake_generate(request):
        assert request.provider == "openai"
        assert request.model == "gpt-4o-mini"
        return _mock_generation_response()

    monkeypatch.setattr(
        "src.api.main.hypothetical_service.generate_hypothetical",
        _fake_generate,
    )

    response = client.post(
        "/generate",
        json={
            "topics": ["negligence"],
            "number_parties": 3,
            "complexity_level": "3",
            "provider": "openai",
            "model": "gpt-4o-mini",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["metadata"]["generation_id"] == 101


def test_generate_endpoint_rejects_invalid_topic(monkeypatch):
    client = TestClient(app)

    monkeypatch.setattr(
        "src.api.main.corpus_service.extract_all_topics",
        AsyncMock(return_value=["negligence"]),
    )

    response = client.post(
        "/generate",
        json={
            "topics": ["battery"],
            "number_parties": 2,
            "complexity_level": "basic",
        },
    )

    assert response.status_code == 400
    assert "Invalid topics" in response.json()["detail"]


def test_batch_generate_endpoint_returns_results(monkeypatch):
    client = TestClient(app)

    monkeypatch.setattr(
        "src.api.main.corpus_service.extract_all_topics",
        AsyncMock(return_value=["negligence"]),
    )
    monkeypatch.setattr(
        "src.api.main.hypothetical_service.generate_hypothetical",
        AsyncMock(return_value=_mock_generation_response()),
    )

    response = client.post(
        "/generate/batch",
        json={
            "configs": [
                {
                    "topic": "negligence",
                    "provider": "ollama",
                    "model": "llama3",
                    "complexity": "intermediate",
                    "parties": 3,
                    "method": "pure_llm",
                }
            ]
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["results"][0]["validation_score"] >= 0.0


def test_report_endpoint_persists_immutable_report(monkeypatch):
    client = TestClient(app)

    monkeypatch.setattr(
        "src.api.main.database_service.save_generation_report",
        AsyncMock(return_value=55),
    )

    response = client.post(
        "/generate/10/report",
        json={
            "issue_types": ["topic_mismatch", "low_quality"],
            "comment": "Needs regeneration with better topic coverage.",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["report_id"] == 55
    assert payload["generation_id"] == 10


def test_regenerate_endpoint_uses_feedback_context(monkeypatch):
    client = TestClient(app)

    monkeypatch.setattr(
        "src.api.main.database_service.get_generation_by_id",
        AsyncMock(
            return_value={
                "id": 42,
                "request": {
                    "topics": ["negligence"],
                    "number_parties": 2,
                    "complexity_level": "basic",
                    "method": "pure_llm",
                    "provider": "ollama",
                    "model": "llama3",
                    "user_preferences": {},
                },
            }
        ),
    )
    monkeypatch.setattr(
        "src.api.main.database_service.build_regeneration_feedback_context",
        AsyncMock(return_value="Issue types: topic_mismatch"),
    )
    monkeypatch.setattr(
        "src.api.main.database_service.get_generation_reports",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        "src.api.main.hypothetical_service.generate_hypothetical",
        AsyncMock(return_value=_mock_generation_response(generation_id=77)),
    )

    response = client.post("/generate/42/regenerate")

    assert response.status_code == 200
    payload = response.json()
    assert payload["source_generation_id"] == 42
    assert payload["feedback_context"] == "Issue types: topic_mismatch"
    assert payload["regenerated"]["metadata"]["generation_id"] == 77


def test_export_endpoint_looks_up_sqlite_generation_id(monkeypatch):
    client = TestClient(app)
    get_generation = AsyncMock(return_value=None)
    monkeypatch.setattr(
        "src.api.main.database_service.get_generation_by_id",
        get_generation,
    )

    response = client.get("/export/321?format=docx")

    assert response.status_code == 404
    assert "321" in response.json()["detail"]
    get_generation.assert_awaited_once_with(321)


def test_report_update_and_delete_are_immutable():
    client = TestClient(app)

    update_resp = client.put("/generate/10/report/99")
    delete_resp = client.delete("/generate/10/report/99")

    assert update_resp.status_code == 403
    assert "immutable" in update_resp.json()["detail"].lower()
    assert delete_resp.status_code == 403
    assert "immutable" in delete_resp.json()["detail"].lower()


def test_regenerate_endpoint_preserves_retry_lineage(monkeypatch):
    client = TestClient(app)
    captured = {}

    monkeypatch.setattr(
        "src.api.main.database_service.get_generation_by_id",
        AsyncMock(
            return_value={
                "id": 44,
                "request": {
                    "topics": ["negligence"],
                    "number_parties": 2,
                    "complexity_level": "basic",
                    "method": "pure_llm",
                    "provider": "ollama",
                    "model": "llama3",
                    "retry_attempt": 2,
                    "user_preferences": {},
                },
            }
        ),
    )
    monkeypatch.setattr(
        "src.api.main.database_service.build_regeneration_feedback_context",
        AsyncMock(return_value="Reporter comment: refine causation"),
    )
    monkeypatch.setattr(
        "src.api.main.database_service.get_generation_reports",
        AsyncMock(
            return_value=[
                GenerationReport(
                    generation_id=44,
                    issue_types=["topic_mismatch"],
                    comment="refine causation",
                    is_locked=True,
                )
            ]
        ),
    )

    async def _fake_generate(request):
        captured["request"] = request
        return _mock_generation_response(generation_id=88)

    monkeypatch.setattr(
        "src.api.main.hypothetical_service.generate_hypothetical",
        _fake_generate,
    )

    response = client.post("/generate/44/regenerate")

    assert response.status_code == 200
    regenerated_request = captured["request"]
    assert regenerated_request.parent_generation_id == 44
    assert regenerated_request.retry_attempt == 3
    assert regenerated_request.retry_reason.startswith("report_feedback")
