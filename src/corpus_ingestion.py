"""Retry, streaming, events, quarantine, and health for corpus ingestion."""

from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, TypeVar

import httpx
from pydantic import BaseModel, Field

DEFAULT_EVENTS_PATH = Path("data/generated/corpus_ingestion_events.jsonl")
DEFAULT_HEALTH_PATH = Path("data/generated/corpus_ingestion_health.json")
DEFAULT_STREAM_THRESHOLD_BYTES = 2 * 1024 * 1024

T = TypeVar("T")


class CorpusIngestionError(Exception):
    """Base corpus ingestion failure."""


class CorpusFetchError(CorpusIngestionError):
    """HTTP or file fetch failure."""


class CorpusParseError(CorpusIngestionError):
    """Fetched content could not be parsed."""


class CorpusValidationError(CorpusIngestionError):
    """Fetched or normalized record failed schema validation."""


class CorpusQuarantineError(CorpusIngestionError):
    """Invalid record could not be quarantined."""


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 4
    base_delay: float = 0.2
    max_delay: float = 5.0
    multiplier: float = 2.0
    jitter: float = 0.1


class IngestionEvent(BaseModel):
    timestamp: str
    event_type: str
    source: str
    message: str
    attempt: int | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class SourceHealth(BaseModel):
    source: str
    last_url: str | None = None
    last_success_at: str | None = None
    last_failure_at: str | None = None
    consecutive_failures: int = 0
    last_error: str | None = None


class IngestionHealth(BaseModel):
    updated_at: str | None = None
    sources: dict[str, SourceHealth] = Field(default_factory=dict)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def emit_event(
    event_type: str,
    *,
    source: str,
    message: str,
    attempt: int | None = None,
    details: dict[str, Any] | None = None,
    events_path: Path = DEFAULT_EVENTS_PATH,
) -> IngestionEvent:
    event = IngestionEvent(
        timestamp=utc_now(),
        event_type=event_type,
        source=source,
        message=message,
        attempt=attempt,
        details=details or {},
    )
    try:
        events_path.parent.mkdir(parents=True, exist_ok=True)
        with events_path.open("a", encoding="utf-8") as handle:
            handle.write(event.model_dump_json() + "\n")
    except OSError:
        pass
    return event


def _read_health_model(health_path: Path) -> IngestionHealth:
    if not health_path.exists():
        return IngestionHealth()
    try:
        payload = json.loads(health_path.read_text(encoding="utf-8"))
        return IngestionHealth.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValueError):
        return IngestionHealth()


def _write_health_model(health: IngestionHealth, health_path: Path) -> None:
    health.updated_at = utc_now()
    health_path.parent.mkdir(parents=True, exist_ok=True)
    health_path.write_text(
        json.dumps(health.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def read_ingestion_health(
    health_path: Path = DEFAULT_HEALTH_PATH,
) -> dict[str, Any]:
    return _read_health_model(health_path).model_dump(mode="json")


def record_source_success(
    source: str,
    url: str,
    *,
    health_path: Path = DEFAULT_HEALTH_PATH,
) -> None:
    health = _read_health_model(health_path)
    current = health.sources.get(source) or SourceHealth(source=source)
    current.last_url = url
    current.last_success_at = utc_now()
    current.consecutive_failures = 0
    current.last_error = None
    health.sources[source] = current
    _write_health_model(health, health_path)


def record_source_failure(
    source: str,
    url: str,
    error: str,
    *,
    health_path: Path = DEFAULT_HEALTH_PATH,
) -> None:
    health = _read_health_model(health_path)
    current = health.sources.get(source) or SourceHealth(source=source)
    current.last_url = url
    current.last_failure_at = utc_now()
    current.consecutive_failures += 1
    current.last_error = error
    health.sources[source] = current
    _write_health_model(health, health_path)


def _status_code(exc: httpx.HTTPStatusError) -> int | None:
    return exc.response.status_code if exc.response is not None else None


def is_retryable_fetch_error(exc: Exception) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        status = _status_code(exc)
        return status in {408, 409, 425, 429} or bool(status and status >= 500)
    return isinstance(exc, (httpx.TimeoutException, httpx.TransportError))


def retry_sync(
    operation: Callable[[], T],
    *,
    source: str,
    url: str = "",
    policy: RetryPolicy | None = None,
    events_path: Path = DEFAULT_EVENTS_PATH,
    sleep: Callable[[float], None] = time.sleep,
    rng: random.Random | None = None,
) -> T:
    policy = policy or RetryPolicy()
    rng = rng or random.Random()
    for attempt in range(1, policy.max_attempts + 1):
        try:
            result = operation()
            if attempt > 1:
                emit_event(
                    "fetch_retry_recovered",
                    source=source,
                    message="retry recovered",
                    attempt=attempt,
                    details={"url": url},
                    events_path=events_path,
                )
            return result
        except Exception as exc:
            retryable = is_retryable_fetch_error(exc)
            if not retryable or attempt >= policy.max_attempts:
                emit_event(
                    "fetch_failed",
                    source=source,
                    message=str(exc),
                    attempt=attempt,
                    details={"url": url, "retryable": retryable},
                    events_path=events_path,
                )
                raise
            delay = min(
                policy.max_delay,
                policy.base_delay * (policy.multiplier ** (attempt - 1)),
            )
            delay += rng.uniform(0, delay * policy.jitter)
            emit_event(
                "fetch_retry",
                source=source,
                message=str(exc),
                attempt=attempt,
                details={"url": url, "delay_seconds": delay},
                events_path=events_path,
            )
            sleep(delay)
    raise CorpusFetchError(f"unreachable retry state for {source}: {url}")


def fetch_http_bytes(
    client: httpx.Client,
    url: str,
    *,
    source: str,
    policy: RetryPolicy | None = None,
    events_path: Path = DEFAULT_EVENTS_PATH,
    health_path: Path = DEFAULT_HEALTH_PATH,
    stream_threshold_bytes: int = DEFAULT_STREAM_THRESHOLD_BYTES,
) -> bytes:
    def operation() -> bytes:
        data = bytearray()
        threshold_logged = False
        with client.stream("GET", url) as response:
            response.raise_for_status()
            total = 0
            for chunk in response.iter_bytes():
                if not chunk:
                    continue
                total += len(chunk)
                data.extend(chunk)
                if not threshold_logged and total >= stream_threshold_bytes:
                    threshold_logged = True
                    emit_event(
                        "fetch_streaming_threshold",
                        source=source,
                        message="response reached streaming threshold",
                        details={"url": url, "bytes": total},
                        events_path=events_path,
                    )
        return bytes(data)

    try:
        payload = retry_sync(
            operation,
            source=source,
            url=url,
            policy=policy,
            events_path=events_path,
        )
        record_source_success(source, url, health_path=health_path)
        return payload
    except httpx.HTTPError as exc:
        record_source_failure(source, url, str(exc), health_path=health_path)
        raise CorpusFetchError(f"failed to fetch {url}: {exc}") from exc


def fetch_http_text(
    client: httpx.Client,
    url: str,
    *,
    source: str,
    encoding: str = "utf-8",
    policy: RetryPolicy | None = None,
    events_path: Path = DEFAULT_EVENTS_PATH,
    health_path: Path = DEFAULT_HEALTH_PATH,
) -> str:
    payload = fetch_http_bytes(
        client,
        url,
        source=source,
        policy=policy,
        events_path=events_path,
        health_path=health_path,
    )
    try:
        return payload.decode(encoding)
    except UnicodeDecodeError as exc:
        raise CorpusParseError(f"failed to decode {url} as {encoding}") from exc


def fetch_http_json(
    client: httpx.Client,
    url: str,
    *,
    source: str,
    policy: RetryPolicy | None = None,
    events_path: Path = DEFAULT_EVENTS_PATH,
    health_path: Path = DEFAULT_HEALTH_PATH,
) -> Any:
    text = fetch_http_text(
        client,
        url,
        source=source,
        policy=policy,
        events_path=events_path,
        health_path=health_path,
    )
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise CorpusParseError(f"failed to parse JSON from {url}") from exc


def quarantine_record(
    quarantine_path: Path,
    *,
    stage: str,
    source: str,
    source_url: str,
    payload: dict[str, Any],
    error: Exception,
    events_path: Path = DEFAULT_EVENTS_PATH,
) -> None:
    record = {
        "timestamp": utc_now(),
        "stage": stage,
        "source": source,
        "source_url": source_url,
        "error_type": type(error).__name__,
        "error": str(error),
        "payload": payload,
    }
    try:
        quarantine_path.parent.mkdir(parents=True, exist_ok=True)
        with quarantine_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")
    except OSError as exc:
        raise CorpusQuarantineError(f"failed to quarantine {source}") from exc
    emit_event(
        "record_quarantined",
        source=source,
        message=str(error),
        details={"stage": stage, "source_url": source_url},
        events_path=events_path,
    )
