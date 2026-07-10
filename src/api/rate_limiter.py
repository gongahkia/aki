"""Small in-process rate limiter for API deployments."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

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
        route_limits: Optional[Dict[str, int]] = None,
    ):
        super().__init__(app)
        self.requests_per_window = max(0, int(requests_per_window))
        self.window_seconds = max(1, int(window_seconds))
        self.max_buckets = max(1, int(max_buckets))
        self.cleanup_interval_seconds = max(1, int(cleanup_interval_seconds))
        self.route_limits = {
            prefix: max(0, int(limit))
            for prefix, limit in (route_limits or {}).items()
            if prefix
        }
        self._buckets: Dict[str, _Bucket] = {}
        self._last_cleanup = time.monotonic()

    async def dispatch(self, request: Request, call_next):
        route_key, limit = self._route_policy(request.url.path)
        if limit == 0:
            return await call_next(request)

        now = time.monotonic()
        self._cleanup(now)
        key = f"{self._client_key(request)}:{route_key}"
        bucket = self._buckets.get(key)
        if bucket is None:
            if len(self._buckets) >= self.max_buckets:
                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": {
                            "code": "rate_limit_capacity",
                            "message": "API is busy. Wait briefly, then retry.",
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
        if bucket.count > limit:
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

    def _route_policy(self, path: str) -> Tuple[str, int]:
        matched = ""
        limit = self.requests_per_window
        for prefix, route_limit in self.route_limits.items():
            if path.startswith(prefix) and len(prefix) > len(matched):
                matched = prefix
                limit = route_limit
        return matched or "*", limit
