"""Benchmark end-to-end API latency for baseline vs fast-mode generation paths."""

import argparse
import asyncio
import json
import os
import statistics
import time
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from src.api.main import app
from src.services.hypothetical_service import GenerationResponse


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    index = int(round((len(values) - 1) * percentile))
    return sorted(values)[index]


def _summarize(latencies_ms: list[float]) -> dict:
    return {
        "count": len(latencies_ms),
        "avg_ms": round(statistics.mean(latencies_ms), 2) if latencies_ms else 0.0,
        "p50_ms": round(_percentile(latencies_ms, 0.50), 2),
        "p95_ms": round(_percentile(latencies_ms, 0.95), 2),
        "min_ms": round(min(latencies_ms), 2) if latencies_ms else 0.0,
        "max_ms": round(max(latencies_ms), 2) if latencies_ms else 0.0,
    }


def _request_headers() -> dict[str, str]:
    api_key = os.environ.get("JIKAI_API_KEY", "").strip()
    if not api_key:
        return {}
    return {"X-API-Key": api_key}


def _run_mode(
    client: TestClient, payload: dict, iterations: int, headers: dict[str, str]
) -> tuple[list[float], dict[int, int], str]:
    latencies_ms: list[float] = []
    status_counts: dict[int, int] = {}
    sample_failure = ""

    for _ in range(iterations):
        start = time.perf_counter()
        response = client.post("/generate", json=payload, headers=headers)
        elapsed_ms = (time.perf_counter() - start) * 1000
        status_code = int(response.status_code)
        status_counts[status_code] = status_counts.get(status_code, 0) + 1
        if status_code == 200:
            latencies_ms.append(elapsed_ms)
        elif not sample_failure:
            sample_failure = response.text[:500]

    return latencies_ms, status_counts, sample_failure


def run_benchmark(iterations: int = 20) -> dict:
    client = TestClient(app, base_url="http://localhost")
    headers = _request_headers()

    async def _fake_generate(request):
        # Simulate heavier baseline path vs faster hypothetical-only mode.
        await asyncio.sleep(0.03 if request.include_analysis else 0.01)
        return GenerationResponse(
            hypothetical="Benchmark hypothetical",
            analysis="Benchmark analysis" if request.include_analysis else "",
            metadata={"generation_id": 9001},
            generation_time=0.1,
            validation_results={"passed": True, "quality_score": 8.0},
        )

    baseline_payload = {
        "topics": ["negligence"],
        "number_parties": 3,
        "complexity_level": "intermediate",
        "include_analysis": True,
    }
    fast_payload = {
        "topics": ["negligence"],
        "number_parties": 3,
        "complexity_level": "intermediate",
        "include_analysis": False,
        "user_preferences": {"prioritize_latency": True, "fast_validation": True},
    }

    with (
        patch(
            "src.api.main.corpus_service.extract_all_topics",
            AsyncMock(return_value=["negligence"]),
        ),
        patch(
            "src.api.main.hypothetical_service.generate_hypothetical",
            AsyncMock(side_effect=_fake_generate),
        ),
    ):
        baseline_latencies, baseline_statuses, baseline_failure = _run_mode(
            client=client,
            payload=baseline_payload,
            iterations=iterations,
            headers=headers,
        )
        fast_latencies, fast_statuses, fast_failure = _run_mode(
            client=client,
            payload=fast_payload,
            iterations=iterations,
            headers=headers,
        )

    if not baseline_latencies or not fast_latencies:
        raise RuntimeError(
            "Latency benchmark did not record successful responses. "
            f"baseline_statuses={baseline_statuses} fast_statuses={fast_statuses} "
            f"baseline_sample_error={baseline_failure!r} fast_sample_error={fast_failure!r}"
        )

    return {
        "iterations": iterations,
        "baseline": _summarize(baseline_latencies),
        "fast_mode": _summarize(fast_latencies),
        "status_codes": {
            "baseline": baseline_statuses,
            "fast_mode": fast_statuses,
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Benchmark generation API latency.")
    parser.add_argument(
        "--iterations",
        type=int,
        default=20,
        help="Number of requests per mode (baseline and fast mode).",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="",
        help="Optional path to write JSON benchmark output.",
    )
    args = parser.parse_args()

    result = run_benchmark(iterations=max(1, args.iterations))
    payload = json.dumps(result, indent=2)
    print(payload)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(payload, encoding="utf-8")


if __name__ == "__main__":
    main()
