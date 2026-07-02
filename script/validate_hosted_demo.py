"""Validate a deployed Jikai hosted demo URL."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from typing import Any, Callable
from urllib import error, parse, request


@dataclass
class Response:
    status: int
    body: str


Fetch = Callable[[str, str, dict[str, Any] | None, int], Response]


def _default_fetch(
    method: str, url: str, payload: dict[str, Any] | None, timeout: int
) -> Response:
    data = None
    headers = {"accept": "application/json, text/html"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["content-type"] = "application/json"
    req = request.Request(url, data=data, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            return Response(resp.status, resp.read().decode("utf-8", errors="replace"))
    except error.HTTPError as exc:
        return Response(exc.code, exc.read().decode("utf-8", errors="replace"))
    except error.URLError as exc:
        return Response(0, str(exc.reason))


def _url(base_url: str, path: str) -> str:
    return parse.urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))


def _json(body: str, label: str) -> dict[str, Any]:
    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label}: invalid JSON") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{label}: JSON root must be object")
    return data


def validate_demo(
    base_url: str,
    *,
    fetch: Fetch = _default_fetch,
    timeout: int = 30,
    generate: bool = False,
) -> list[str]:
    errors: list[str] = []

    health = fetch("GET", _url(base_url, "/health"), None, timeout)
    if health.status != 200:
        errors.append(f"/health returned {health.status}")
    else:
        try:
            _json(health.body, "/health")
        except ValueError as exc:
            errors.append(str(exc))

    demo = fetch("GET", _url(base_url, "/demo"), None, timeout)
    if demo.status != 200:
        errors.append(f"/demo returned {demo.status}")
    elif "Jikai Demo" not in demo.body or "/workflow/generate" not in demo.body:
        errors.append("/demo missing expected browser shell")

    pipeline = fetch("GET", _url(base_url, "/demo/pipeline"), None, timeout)
    if pipeline.status != 200:
        errors.append(f"/demo/pipeline returned {pipeline.status}")
    elif "Jikai Pipeline Trace" not in pipeline.body:
        errors.append("/demo/pipeline missing expected browser shell")

    trace = fetch("GET", _url(base_url, "/demo/pipeline/trace"), None, timeout)
    if trace.status != 200:
        errors.append(f"/demo/pipeline/trace returned {trace.status}")
    else:
        try:
            trace_data = _json(trace.body, "/demo/pipeline/trace")
            if trace_data.get("schema_version") != "1.0":
                errors.append("/demo/pipeline/trace schema_version mismatch")
            if not trace_data.get("stages"):
                errors.append("/demo/pipeline/trace missing stages")
        except ValueError as exc:
            errors.append(str(exc))

    if generate:
        generation = fetch(
            "POST",
            _url(base_url, "/workflow/generate"),
            _generation_payload(),
            max(timeout, 120),
        )
        if generation.status != 200:
            errors.append(f"/workflow/generate returned {generation.status}")
        else:
            try:
                data = _json(generation.body, "/workflow/generate")
                for key in ("hypothetical", "model_answer", "validation_results"):
                    if key not in data:
                        errors.append(f"/workflow/generate missing {key}")
            except ValueError as exc:
                errors.append(str(exc))

    return errors


def _generation_payload() -> dict[str, Any]:
    return {
        "topics": ["negligence", "causation"],
        "corpus_pack": "sg_tort",
        "jurisdiction": "sg",
        "subject": "tort",
        "law_domain": "tort",
        "subtopics": ["duty of care", "remoteness"],
        "number_parties": 3,
        "complexity_level": "intermediate",
        "sample_size": 3,
        "include_analysis": True,
        "user_preferences": {"timeout_seconds": 90},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_url")
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--generate", action="store_true")
    args = parser.parse_args()

    errors = validate_demo(args.base_url, timeout=args.timeout, generate=args.generate)
    if errors:
        for item in errors:
            print(f"ERROR: {item}", file=sys.stderr)
        return 1
    print("OK: hosted demo")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
