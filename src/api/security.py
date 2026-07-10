"""Hosted API security middleware."""

from __future__ import annotations

import secrets
from typing import Dict, Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from ..config import settings

PUBLIC_EXACT_ROUTES = {
    ("GET", "/health"),
    ("GET", "/version"),
    ("POST", "/workflow/generate"),
}
PUBLIC_PREFIX_ROUTES = {
    ("GET", "/demo"),
    ("POST", "/demo/pipeline/trace"),
}


def is_hosted_api() -> bool:
    return bool(
        settings.api.hosted_mode
        or str(settings.environment).lower() in {"staging", "production"}
    )


class HostedAdminAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not is_hosted_api() or _is_public_request(request):
            return await call_next(request)

        expected = _admin_api_key()
        if not expected:
            return _security_error(
                403,
                "admin_api_key_missing",
                "Admin API routes are disabled until API_ADMIN_KEY is configured.",
            )

        provided = _request_api_key(request)
        if not provided or not secrets.compare_digest(provided, expected):
            return _security_error(
                401,
                "admin_auth_required",
                "Admin API key required.",
                authenticate=True,
            )
        return await call_next(request)


class RequestBodySizeLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        *,
        max_body_bytes: int,
        route_body_limits: Optional[Dict[str, int]] = None,
    ):
        super().__init__(app)
        self.max_body_bytes = max(0, int(max_body_bytes))
        self.route_body_limits = {
            prefix: max(0, int(limit))
            for prefix, limit in (route_body_limits or {}).items()
            if prefix
        }

    async def dispatch(self, request: Request, call_next):
        limit = self._limit_for_path(request.url.path)
        if limit == 0:
            return await call_next(request)

        raw_length = request.headers.get("content-length")
        if raw_length:
            try:
                length = int(raw_length)
            except ValueError:
                return _body_size_error(limit)
            if length > limit:
                return _body_size_error(limit)
        return await call_next(request)

    def _limit_for_path(self, path: str) -> int:
        matched = ""
        limit = self.max_body_bytes
        for prefix, route_limit in self.route_body_limits.items():
            if path.startswith(prefix) and len(prefix) > len(matched):
                matched = prefix
                limit = route_limit
        return limit


def _is_public_request(request: Request) -> bool:
    if request.method == "OPTIONS":
        return True
    route = (request.method, request.url.path.rstrip("/") or "/")
    if route in PUBLIC_EXACT_ROUTES:
        return True
    for method, prefix in PUBLIC_PREFIX_ROUTES:
        if request.method == method and request.url.path.startswith(prefix):
            return True
    return False


def _admin_api_key() -> str:
    return str(settings.api.admin_api_key or "").strip()


def _request_api_key(request: Request) -> Optional[str]:
    header_key = request.headers.get("x-api-key")
    if header_key:
        return header_key.strip()
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return None


def _security_error(
    status_code: int,
    code: str,
    message: str,
    *,
    authenticate: bool = False,
) -> JSONResponse:
    headers = {"WWW-Authenticate": "Bearer"} if authenticate else None
    return JSONResponse(
        status_code=status_code,
        content={"detail": {"code": code, "message": message, "retryable": False}},
        headers=headers,
    )


def _body_size_error(limit: int) -> JSONResponse:
    return JSONResponse(
        status_code=413,
        content={
            "detail": {
                "code": "request_body_too_large",
                "message": f"Request body exceeds {limit} bytes.",
                "retryable": False,
            }
        },
    )
