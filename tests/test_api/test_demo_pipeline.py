from fastapi.testclient import TestClient

from src.api.main import create_app


def test_generation_page_serves_public_demo_shell():
    client = TestClient(create_app())

    response = client.get("/demo")
    script = client.get("/demo/static/app.js")
    css = client.get("/demo/static/app.css")

    assert response.status_code == 200
    assert "Ask for a Singapore tort hypothetical" in response.text
    assert "/demo/static/app.css" in response.text
    assert "/demo/static/app.js" in response.text
    assert "Load sample" in response.text
    assert "Local run history" in response.text
    assert script.status_code == 200
    assert "indexedDB.open" in script.text
    assert "/workflow/generate" in script.text
    assert "/demo/pipeline/trace" in script.text
    assert css.status_code == 200
    assert ".trace-panel" in css.text
    assert ".factory-line" in css.text
    assert "crate-run" in css.text


def test_pipeline_page_redirects_to_chat_shell():
    client = TestClient(create_app())

    response = client.get("/demo/pipeline", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/demo"


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
