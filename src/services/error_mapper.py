"""Centralized exception mapping for consistent user-facing errors."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ErrorMapping:
    """Normalized user-facing error payload used by API and TUI."""

    code: str
    message: str
    http_status: int
    hint: str = ""
    retryable: bool = False


def _extract_message(error: Any) -> str:
    if error is None:
        return ""

    detail = getattr(error, "detail", None)
    if detail is not None:
        if isinstance(detail, dict):
            if "error" in detail:
                return str(detail["error"])
            if "detail" in detail:
                return str(detail["detail"])
        return str(detail)

    if isinstance(error, dict):
        if "error" in error:
            return str(error["error"])
        if "detail" in error:
            return str(error["detail"])

    return str(error)


def map_exception(error: Any, *, default_status: int = 500) -> ErrorMapping:
    """Map raw exceptions/messages into stable user-facing error semantics."""
    raw_message = _extract_message(error).strip()
    lowered = raw_message.lower()

    if any(
        token in lowered
        for token in ("api key", "apikey", "authentication", "unauthorized")
    ):
        return ErrorMapping(
            code="provider_auth_error",
            message="Provider authentication failed. Update API credentials and retry.",
            http_status=401,
            hint="Go to More -> Settings and verify the provider API keys.",
        )

    if "model" in lowered and any(
        token in lowered for token in ("not found", "does not exist", "not available")
    ):
        return ErrorMapping(
            code="provider_model_unavailable",
            message="Selected model is unavailable for the current provider.",
            http_status=400,
            hint="Open More -> Providers and choose an available model.",
        )

    if any(token in lowered for token in ("rate limit", "too many requests")):
        return ErrorMapping(
            code="provider_rate_limited",
            message="Provider rate limit reached. Wait briefly, then retry.",
            http_status=429,
            hint="Retry after a short delay or switch to another provider.",
            retryable=True,
        )

    if any(token in lowered for token in ("timeout", "timed out")):
        return ErrorMapping(
            code="provider_timeout",
            message="Provider request timed out. Retry or lower generation complexity.",
            http_status=504,
            hint="Enable fast mode or reduce complexity to cut generation time.",
            retryable=True,
        )

    if any(
        token in lowered
        for token in (
            "connection",
            "refused",
            "unreachable",
            "all connection attempts failed",
            "network",
        )
    ):
        return ErrorMapping(
            code="provider_connection_error",
            message="Could not connect to the selected provider.",
            http_status=503,
            hint="Check that the provider service is running and reachable.",
            retryable=True,
        )

    if "circuit-broken" in lowered or "unhealthy" in lowered:
        return ErrorMapping(
            code="provider_unhealthy",
            message="Selected provider is temporarily unavailable.",
            http_status=503,
            hint="Retry shortly or switch providers.",
            retryable=True,
        )

    if "provider" in lowered and "not available" in lowered:
        return ErrorMapping(
            code="provider_unavailable",
            message="Selected provider is unavailable in the current runtime.",
            http_status=503,
            hint="Open More -> Providers to choose another configured provider.",
        )

    if default_status >= 500:
        return ErrorMapping(
            code="internal_error",
            message="Internal server error",
            http_status=default_status,
        )

    return ErrorMapping(
        code="request_error",
        message=raw_message or "Request failed",
        http_status=default_status,
    )
