import json

from script.validate_hosted_demo import Response, validate_demo


def _fetch_ok(method, url, payload, timeout):
    if url.endswith("/health"):
        return Response(200, json.dumps({"status": "healthy"}))
    if url.endswith("/demo"):
        return Response(200, "Jikai Demo /workflow/generate")
    if url.endswith("/demo/pipeline"):
        return Response(200, "Jikai Pipeline Trace")
    if url.endswith("/demo/pipeline/trace"):
        return Response(200, json.dumps({"schema_version": "1.0", "stages": [{}]}))
    if url.endswith("/workflow/generate"):
        return Response(
            200,
            json.dumps(
                {
                    "hypothetical": "x",
                    "model_answer": "y",
                    "validation_results": {},
                }
            ),
        )
    return Response(404, "")


def test_validate_demo_smoke_without_generation():
    assert validate_demo("https://example.test", fetch=_fetch_ok) == []


def test_validate_demo_generation_path():
    assert validate_demo("https://example.test", fetch=_fetch_ok, generate=True) == []


def test_validate_demo_reports_missing_shell():
    def fetch(method, url, payload, timeout):
        if url.endswith("/health"):
            return Response(200, "{}")
        if url.endswith("/demo"):
            return Response(200, "wrong")
        if url.endswith("/demo/pipeline"):
            return Response(200, "wrong")
        if url.endswith("/demo/pipeline/trace"):
            return Response(200, json.dumps({"schema_version": "1.0", "stages": [{}]}))
        return Response(404, "")

    errors = validate_demo("https://example.test", fetch=fetch)

    assert "/demo missing expected browser shell" in errors
    assert "/demo/pipeline missing expected browser shell" in errors


def test_validate_demo_reports_generation_failure():
    def fetch(method, url, payload, timeout):
        if url.endswith("/workflow/generate"):
            return Response(500, "{}")
        return _fetch_ok(method, url, payload, timeout)

    errors = validate_demo("https://example.test", fetch=fetch, generate=True)

    assert "/workflow/generate returned 500" in errors


def test_validate_demo_reports_unreachable_host():
    def fetch(method, url, payload, timeout):
        return Response(0, "connection refused")

    errors = validate_demo("https://example.test", fetch=fetch)

    assert "/health returned 0" in errors


def test_validate_static_demo_page():
    def fetch(method, url, payload, timeout):
        return Response(
            200,
            "Jikai Hosted Demo Generate Model Answer Export Anki TSV Public fixture Generation Failed",
        )

    assert validate_demo("https://example.test/jikai/", fetch=fetch, static=True) == []


def test_validate_static_demo_reports_missing_marker():
    def fetch(method, url, payload, timeout):
        return Response(200, "Jikai Hosted Demo")

    errors = validate_demo("https://example.test/jikai/", fetch=fetch, static=True)

    assert "/ missing Model Answer" in errors
