from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.rate_limiter import InMemoryRateLimitMiddleware
from src.api.security import RequestBodySizeLimitMiddleware


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


def test_rate_limiter_supports_route_specific_limits():
    app = FastAPI()
    app.add_middleware(
        InMemoryRateLimitMiddleware,
        requests_per_window=100,
        window_seconds=60,
        max_buckets=10,
        cleanup_interval_seconds=60,
        route_limits={"/hot": 1},
    )

    @app.get("/hot")
    async def hot():
        return {"ok": True}

    @app.get("/cold")
    async def cold():
        return {"ok": True}

    client = TestClient(app)

    assert client.get("/hot").status_code == 200
    assert client.get("/hot").status_code == 429
    assert client.get("/cold").status_code == 200


def test_body_size_limit_returns_413_for_oversized_route_body():
    app = FastAPI()
    app.add_middleware(
        RequestBodySizeLimitMiddleware,
        max_body_bytes=100,
        route_body_limits={"/upload": 3},
    )

    @app.post("/upload")
    async def upload():
        return {"ok": True}

    client = TestClient(app)
    response = client.post("/upload", content="abcd")

    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "request_body_too_large"
