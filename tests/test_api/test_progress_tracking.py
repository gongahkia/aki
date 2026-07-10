from fastapi.testclient import TestClient

import src.services as services
from src.api.main import create_app


class StubDatabaseService:
    def __init__(self):
        self.saved_attempt = None
        self.summary_limit = None

    async def save_student_attempt(self, attempt):
        self.saved_attempt = attempt
        return 123

    async def get_progress_summary(self, limit=10):
        self.summary_limit = limit
        return {
            "recent_attempts": [
                {
                    "id": 123,
                    "topics": ["negligence"],
                    "self_rating": 2,
                    "rubric_misses": ["issue_spotting"],
                }
            ],
            "weak_topics": [{"topic": "negligence", "repeated_weak_topic": True}],
            "spaced_repetition_queue": [{"topic": "negligence", "due_now": True}],
            "study_plan": {"markdown": "- negligence"},
        }


def test_progress_attempt_endpoint_saves_student_attempt(monkeypatch):
    stub = StubDatabaseService()
    monkeypatch.setattr(services, "database_service", stub)
    client = TestClient(create_app())

    response = client.post(
        "/db/progress/attempts",
        json={
            "topics": ["Negligence"],
            "self_rating": 2,
            "rubric_misses": ["issue spotting"],
            "elapsed_seconds": 90,
        },
    )

    assert response.status_code == 200
    assert response.json() == {"attempt_id": 123}
    assert stub.saved_attempt is not None
    assert stub.saved_attempt.topics == ["Negligence"]
    assert stub.saved_attempt.self_rating == 2
    assert stub.saved_attempt.rubric_misses == ["issue spotting"]


def test_progress_summary_endpoint_exposes_attempt_history(monkeypatch):
    stub = StubDatabaseService()
    monkeypatch.setattr(services, "database_service", stub)
    client = TestClient(create_app())

    response = client.get("/db/progress/summary", params={"limit": 2})

    assert response.status_code == 200
    payload = response.json()
    assert stub.summary_limit == 2
    assert payload["recent_attempts"][0]["topics"] == ["negligence"]
    assert payload["weak_topics"][0]["topic"] == "negligence"
