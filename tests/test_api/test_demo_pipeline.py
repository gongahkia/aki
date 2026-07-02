from fastapi.testclient import TestClient

from src.api.main import create_app


def test_generation_page_serves_public_demo_shell():
    client = TestClient(create_app())

    response = client.get("/demo")

    assert response.status_code == 200
    assert "Jikai Practice" in response.text
    assert "/workflow/generate" in response.text
    assert "Load sample" in response.text
    assert "Question setup" in response.text
    assert "server-side provider" in response.text


def test_pipeline_page_serves_visual_shell():
    client = TestClient(create_app())

    response = client.get("/demo/pipeline")

    assert response.status_code == 200
    assert "Jikai Trace" in response.text
    assert "/demo/pipeline/trace" in response.text


def test_pipeline_trace_endpoint_returns_stage_json():
    client = TestClient(create_app())

    response = client.get(
        "/demo/pipeline/trace",
        params={"topics": "negligence, causation"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "fixture"
    assert payload["summary"]["passed"] is True
    assert [stage["id"] for stage in payload["stages"]][-3:] == [
        "generation",
        "validation",
        "study",
    ]
    study_stage = payload["stages"][-1]
    assert "anki_tsv_preview" in study_stage["details"]
    assert "model_answer" in study_stage["details"]


def test_pipeline_trace_endpoint_can_expose_prompt():
    client = TestClient(create_app())

    response = client.get(
        "/demo/pipeline/trace",
        params={"topics": "negligence, causation", "expose_prompt": "true"},
    )

    assert response.status_code == 200
    prompt_stage = next(
        stage for stage in response.json()["stages"] if stage["id"] == "prompt"
    )
    assert prompt_stage["details"]["redacted"] is False
    assert "user_prompt" in prompt_stage["details"]
