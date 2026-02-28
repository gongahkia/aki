"""Tests for centralized exception mapping."""

from fastapi import HTTPException

from src.services.error_mapper import map_exception


def test_maps_provider_auth_error():
    mapped = map_exception(RuntimeError("OpenAI API key missing"), default_status=500)

    assert mapped.code == "provider_auth_error"
    assert mapped.http_status == 401
    assert "authentication failed" in mapped.message.lower()


def test_maps_connection_error():
    mapped = map_exception(
        RuntimeError("Connection refused while contacting provider"), default_status=500
    )

    assert mapped.code == "provider_connection_error"
    assert mapped.http_status == 503


def test_preserves_client_error_message_for_unknowns():
    mapped = map_exception("Invalid topics: ['foo']", default_status=400)

    assert mapped.code == "request_error"
    assert mapped.http_status == 400
    assert mapped.message == "Invalid topics: ['foo']"


def test_hides_unknown_server_error_message():
    mapped = map_exception(RuntimeError("sensitive stack details"), default_status=500)

    assert mapped.code == "internal_error"
    assert mapped.http_status == 500
    assert mapped.message == "Internal server error"


def test_extracts_http_exception_detail():
    exc = HTTPException(status_code=429, detail="Rate limit exceeded")
    mapped = map_exception(exc, default_status=429)

    assert mapped.code == "provider_rate_limited"
    assert mapped.http_status == 429
