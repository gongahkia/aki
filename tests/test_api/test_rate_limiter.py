from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.rate_limiter import InMemoryRateLimitMiddleware


def test_rate_limiter_returns_retryable_429_after_limit():
    app = FastAPI()
    app.add_middleware(
        InMemoryRateLimitMiddleware,
        requests_per_window=2,
        window_seconds=60,
        max_buckets=10,
        cleanup_interval_seconds=60,
    )

    @app.get("/ping")
    async def ping():
        return {"ok": True}

    client = TestClient(app)

    assert (
        client.get("/ping", headers={"x-forwarded-for": "203.0.113.9"}).status_code
        == 200
    )
    assert (
        client.get("/ping", headers={"x-forwarded-for": "203.0.113.9"}).status_code
        == 200
    )
    limited = client.get("/ping", headers={"x-forwarded-for": "203.0.113.9"})

    assert limited.status_code == 429
    assert limited.headers["retry-after"]
    assert limited.json()["detail"]["code"] == "rate_limited"
