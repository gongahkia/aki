"""Small in-process rate limiter for public demo deployments."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


@dataclass
class _Bucket:
    window_start: float
    count: int
    last_seen: float


class InMemoryRateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        *,
        requests_per_window: int,
        window_seconds: int,
        max_buckets: int,
        cleanup_interval_seconds: int,
    ):
        super().__init__(app)
        self.requests_per_window = max(0, int(requests_per_window))
        self.window_seconds = max(1, int(window_seconds))
        self.max_buckets = max(1, int(max_buckets))
        self.cleanup_interval_seconds = max(1, int(cleanup_interval_seconds))
        self._buckets: Dict[str, _Bucket] = {}
        self._last_cleanup = time.monotonic()

    async def dispatch(self, request: Request, call_next):
        if self.requests_per_window == 0:
            return await call_next(request)

        now = time.monotonic()
        self._cleanup(now)
        key = self._client_key(request)
        bucket = self._buckets.get(key)
        if bucket is None:
            if len(self._buckets) >= self.max_buckets:
                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": {
                            "code": "rate_limit_capacity",
                            "message": "Demo is busy. Wait briefly, then retry.",
                            "retryable": True,
                        }
                    },
                    headers={"Retry-After": str(self.window_seconds)},
                )
            bucket = _Bucket(window_start=now, count=0, last_seen=now)
            self._buckets[key] = bucket

        if now - bucket.window_start >= self.window_seconds:
            bucket.window_start = now
            bucket.count = 0

        bucket.count += 1
        bucket.last_seen = now
        if bucket.count > self.requests_per_window:
            retry_after = max(1, int(self.window_seconds - (now - bucket.window_start)))
            return JSONResponse(
                status_code=429,
                content={
                    "detail": {
                        "code": "rate_limited",
                        "message": "Rate limit reached. Wait briefly, then retry.",
                        "retryable": True,
                        "retry_after_seconds": retry_after,
                    }
                },
                headers={"Retry-After": str(retry_after)},
            )

        return await call_next(request)

    def _cleanup(self, now: float) -> None:
        if now - self._last_cleanup < self.cleanup_interval_seconds:
            return
        cutoff = now - self.window_seconds
        self._buckets = {
            key: bucket
            for key, bucket in self._buckets.items()
            if bucket.last_seen >= cutoff
        }
        self._last_cleanup = now

    @staticmethod
    def _client_key(request: Request) -> str:
        for header in ("cf-connecting-ip", "fly-client-ip", "x-forwarded-for"):
            value = request.headers.get(header)
            if value:
                return value.split(",", 1)[0].strip()
        client = request.client
        return client.host if client else "unknown"
