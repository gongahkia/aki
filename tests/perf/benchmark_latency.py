"""Benchmark Rich-generation flow latency for baseline, fast, and realism-first presets."""

import argparse
import asyncio
import json
import statistics
import time
from pathlib import Path
from unittest.mock import AsyncMock, patch

from src.services.hypothetical_service import (
    GenerationRequest,
    ValidationResult,
    hypothetical_service,
)


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


def _is_realism_first(request: GenerationRequest) -> bool:
    preferences = request.user_preferences or {}
    temperature = float(preferences.get("temperature", 0.7))
    return bool(
        request.include_analysis
        and request.method == "hybrid"
        and request.number_parties == 4
        and request.complexity_level == "expert"
        and temperature <= 0.21
    )


def _is_fast_mode(request: GenerationRequest) -> bool:
    preferences = request.user_preferences or {}
    return bool(
        (not request.include_analysis)
        or preferences.get("prioritize_latency")
        or preferences.get("fast_validation")
    )


async def _run_mode(payload: dict, iterations: int) -> tuple[list[float], int, str]:
    latencies_ms: list[float] = []
    failure_count = 0
    sample_failure = ""

    for _ in range(iterations):
        request = GenerationRequest(**payload)
        started = time.perf_counter()
        try:
            await hypothetical_service.generate_hypothetical(request)
            latencies_ms.append((time.perf_counter() - started) * 1000)
        except Exception as exc:  # noqa: BLE001 - benchmark should continue on failures
            failure_count += 1
            if not sample_failure:
                sample_failure = str(exc)

    return latencies_ms, failure_count, sample_failure


def run_benchmark(iterations: int = 20) -> dict:
    async def _fake_context(_request: GenerationRequest):
        await asyncio.sleep(0.003)
        return []

    async def _fake_generate_text(request: GenerationRequest, _context_entries):
        if _is_realism_first(request):
            await asyncio.sleep(0.045)
        elif _is_fast_mode(request):
            await asyncio.sleep(0.010)
        else:
            await asyncio.sleep(0.022)
        return (
            "In Singapore, the plaintiff alleged negligence against the defendant "
            "after an accident causing injury and damages. "
            "The case involved duty of care, breach, and causation."
        )

    async def _fake_validate(
        request: GenerationRequest,
        _hypothetical: str,
        _context_entries,
    ) -> ValidationResult:
        if _is_realism_first(request):
            await asyncio.sleep(0.018)
            realism_score = 0.88
            exam_score = 0.82
            quality_score = 8.8
        elif _is_fast_mode(request):
            await asyncio.sleep(0.006)
            realism_score = 0.68
            exam_score = 0.66
            quality_score = 7.4
        else:
            await asyncio.sleep(0.011)
            realism_score = 0.75
            exam_score = 0.72
            quality_score = 8.0

        return ValidationResult(
            adherence_check={
                "passed": True,
                "quality_gate": {"passed": True, "failed_checks": []},
            },
            similarity_check={"passed": True, "max_similarity": 0.12},
            quality_score=quality_score,
            legal_realism_score=realism_score,
            exam_likeness_score=exam_score,
            passed=True,
        )

    async def _fake_analysis(request: GenerationRequest, _hypothetical: str) -> str:
        if _is_realism_first(request):
            await asyncio.sleep(0.020)
        else:
            await asyncio.sleep(0.012)
        return "IRAC analysis output."

    baseline_payload = {
        "topics": ["negligence"],
        "number_parties": 3,
        "complexity_level": "intermediate",
        "method": "pure_llm",
        "include_analysis": True,
        "user_preferences": {"disable_cache": True},
    }
    fast_payload = {
        "topics": ["negligence"],
        "number_parties": 3,
        "complexity_level": "intermediate",
        "method": "pure_llm",
        "include_analysis": False,
        "user_preferences": {
            "prioritize_latency": True,
            "fast_validation": True,
            "disable_cache": True,
        },
    }
    realism_first_payload = {
        "topics": ["negligence"],
        "number_parties": 4,
        "complexity_level": "5",
        "method": "hybrid",
        "include_analysis": True,
        "user_preferences": {
            "temperature": 0.2,
            "red_herrings": False,
            "disable_cache": True,
        },
    }

    async def _run() -> dict:
        with (
            patch.object(
                hypothetical_service,
                "_get_relevant_context",
                AsyncMock(side_effect=_fake_context),
            ),
            patch.object(
                hypothetical_service,
                "_generate_hypothetical_text",
                AsyncMock(side_effect=_fake_generate_text),
            ),
            patch.object(
                hypothetical_service,
                "_validate_hypothetical",
                AsyncMock(side_effect=_fake_validate),
            ),
            patch.object(
                hypothetical_service,
                "_generate_legal_analysis",
                AsyncMock(side_effect=_fake_analysis),
            ),
            patch.object(
                hypothetical_service.database_service,
                "save_generation",
                AsyncMock(return_value=9001),
            ),
        ):
            baseline_latencies, baseline_failures, baseline_error = await _run_mode(
                baseline_payload, iterations
            )
            fast_latencies, fast_failures, fast_error = await _run_mode(
                fast_payload, iterations
            )
            realism_latencies, realism_failures, realism_error = await _run_mode(
                realism_first_payload, iterations
            )

        if not baseline_latencies or not fast_latencies or not realism_latencies:
            raise RuntimeError(
                "Latency benchmark did not record successful responses for all modes. "
                f"baseline_failures={baseline_failures} fast_failures={fast_failures} "
                f"realism_first_failures={realism_failures} "
                f"baseline_error={baseline_error!r} fast_error={fast_error!r} "
                f"realism_first_error={realism_error!r}"
            )

        return {
            "iterations": iterations,
            "baseline": _summarize(baseline_latencies),
            "fast_mode": _summarize(fast_latencies),
            "realism_first": _summarize(realism_latencies),
            "failures": {
                "baseline": baseline_failures,
                "fast_mode": fast_failures,
                "realism_first": realism_failures,
            },
        }

    return asyncio.run(_run())


def main():
    parser = argparse.ArgumentParser(
        description="Benchmark Rich-generation flow latency profiles."
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=20,
        help="Number of generation runs per mode.",
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
