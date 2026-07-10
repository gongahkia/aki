from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from src.api.main import create_app
from src.config import settings
from src.services import workflow_facade


def _hosted(monkeypatch, *, api_key=None):
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings.api, "hosted_mode", True)
    monkeypatch.setattr(settings.api, "admin_api_key", api_key)


def test_hosted_admin_routes_require_api_key(monkeypatch):
    _hosted(monkeypatch, api_key="secret")
    client = TestClient(create_app())

    missing = client.post("/llm/select-provider", json={"name": "openai"})
    wrong = client.post(
        "/llm/select-provider",
        json={"name": "openai"},
        headers={"x-api-key": "wrong"},
    )

    assert missing.status_code == 401
    assert wrong.status_code == 401
    assert missing.json()["detail"]["code"] == "admin_auth_required"

    allowed = client.get(
        "/llm/session-cost", headers={"authorization": "Bearer secret"}
    )
    assert allowed.status_code == 200
    assert "total_cost_usd" in allowed.json()


def test_hosted_admin_routes_disable_without_configured_key(monkeypatch):
    _hosted(monkeypatch, api_key=None)
    client = TestClient(create_app())

    response = client.post("/corpus/add", json={"text": "x", "topics": ["negligence"]})

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "admin_api_key_missing"


def test_hosted_generate_is_public_and_strips_provider(monkeypatch):
    _hosted(monkeypatch, api_key=None)
    generate = AsyncMock(
        return_value=SimpleNamespace(
            request=SimpleNamespace(practice_mode="issue_spotting"),
            response=SimpleNamespace(
                hypothetical="Fact pattern.",
                analysis="",
                model_answer="",
                generation_time=0.01,
                validation_results={},
                metadata={},
            ),
        )
    )
    monkeypatch.setattr(workflow_facade, "generate_generation", generate)
    client = TestClient(create_app())

    response = client.post(
        "/workflow/generate",
        json={"topics": ["negligence"], "provider": "openai", "model": "gpt-4o"},
    )

    assert response.status_code == 200
    assert generate.await_args is not None
    request = generate.await_args.args[0]
    assert request.provider is None
    assert request.model is None


def test_hosted_demo_trace_forces_fixture_redaction(monkeypatch):
    _hosted(monkeypatch, api_key=None)
    client = TestClient(create_app())

    response = client.get(
        "/demo/pipeline/trace",
        params={
            "topics": "negligence, causation",
            "live": "true",
            "expose_prompt": "true",
            "expose_provider": "true",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "fixture"
    assert payload["redaction"]["prompt_exposed"] is False
    assert payload["redaction"]["provider_exposed"] is False
