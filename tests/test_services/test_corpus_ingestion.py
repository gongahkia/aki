import json

import httpx
import pytest

from src.corpus_ingestion import (
    CorpusParseError,
    RetryPolicy,
    fetch_http_bytes,
    fetch_http_json,
    read_ingestion_health,
    record_source_failure,
    record_source_success,
    retry_sync,
)


class _FakeResponse:
    def __init__(self, chunks, status_code=200):
        self._chunks = chunks
        self.status_code = status_code

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def raise_for_status(self):
        if self.status_code < 400:
            return
        request = httpx.Request("GET", "https://example.test/case")
        response = httpx.Response(self.status_code, request=request)
        raise httpx.HTTPStatusError("bad status", request=request, response=response)

    def iter_bytes(self):
        yield from self._chunks


class _FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.get_called = False

    def get(self, *_args, **_kwargs):
        self.get_called = True
        raise AssertionError("plain get should not be used")

    def stream(self, _method, _url):
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def test_retry_sync_survives_thirty_percent_transient_failures(tmp_path):
    attempts: dict[int, int] = {}
    transient_failure_indexes = {0, 3, 6}
    policy = RetryPolicy(max_attempts=3, base_delay=0, jitter=0)

    results: list[int] = []
    for index in range(10):

        def operation(i=index):
            attempts[i] = attempts.get(i, 0) + 1
            if i in transient_failure_indexes and attempts[i] == 1:
                raise httpx.ConnectError("temporary network failure")
            return i

        results.append(
            retry_sync(
                operation,
                source="test:network",
                url=f"https://example.test/{index}",
                policy=policy,
                events_path=tmp_path / "events.jsonl",
                sleep=lambda _delay: None,
            )
        )

    assert results == list(range(10))
    assert sum(attempts.values()) == 13
    assert (tmp_path / "events.jsonl").exists()


def test_fetch_http_bytes_streams_and_records_health(tmp_path):
    client = _FakeClient([_FakeResponse([b"abc", b"def"])])
    body = fetch_http_bytes(
        client,
        "https://example.test/case",
        source="test:source",
        events_path=tmp_path / "events.jsonl",
        health_path=tmp_path / "health.json",
        stream_threshold_bytes=4,
    )

    assert body == b"abcdef"
    assert client.get_called is False
    events = [
        json.loads(line)
        for line in (tmp_path / "events.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert events[0]["event_type"] == "fetch_streaming_threshold"
    health = read_ingestion_health(tmp_path / "health.json")
    assert health["sources"]["test:source"]["last_success_at"]
    assert health["sources"]["test:source"]["consecutive_failures"] == 0


def test_fetch_http_json_raises_parse_error_for_invalid_json(tmp_path):
    client = _FakeClient([_FakeResponse([b"{"])])

    with pytest.raises(CorpusParseError):
        fetch_http_json(
            client,
            "https://example.test/case",
            source="test:source",
            events_path=tmp_path / "events.jsonl",
            health_path=tmp_path / "health.json",
        )


def test_record_source_failure_preserves_previous_success(tmp_path):
    health_path = tmp_path / "health.json"
    record_source_success(
        "test:source", "https://example.test/a", health_path=health_path
    )
    record_source_failure(
        "test:source",
        "https://example.test/b",
        "boom",
        health_path=health_path,
    )

    health = read_ingestion_health(health_path)
    source = health["sources"]["test:source"]
    assert source["last_success_at"]
    assert source["last_failure_at"]
    assert source["consecutive_failures"] == 1
    assert source["last_error"] == "boom"
