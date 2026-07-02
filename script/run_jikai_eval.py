#!/usr/bin/env python3
"""Run Jikai eval sweeps and emit result/leaderboard artifacts."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Iterator

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import settings  # noqa: E402
from src.evals import EvalRequest, run_eval  # noqa: E402
from src.evals.runner import load_dataset  # noqa: E402

METRICS = [
    "retrieval_recall_at_k",
    "retrieval_mrr",
    "retrieval_ndcg",
    "ragas_faithfulness",
    "citation_accuracy",
    "hallucination_profile",
    "irac_completeness",
]


def _split(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _metric(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 6)


def _dry_metrics(provider: str, retrieval: str, backend: str) -> dict[str, float]:
    base = {
        "retrieval_recall_at_k": 0.58,
        "retrieval_mrr": 0.46,
        "retrieval_ndcg": 0.5,
        "ragas_faithfulness": 0.62,
        "citation_accuracy": 0.57,
        "hallucination_profile": 0.66,
        "irac_completeness": 0.54,
    }
    retrieval_bonus = {"bm25": 0.0, "dense": 0.03, "hybrid": 0.07}.get(retrieval, 0.0)
    backend_bonus = {"baseline": 0.0, "structured": 0.06, "refine": 0.12}.get(
        backend, 0.0
    )
    provider_bonus = {"ollama": 0.0, "openai": 0.04, "anthropic": 0.035}.get(
        provider, 0.0
    )
    return {
        name: _metric(value + retrieval_bonus + backend_bonus + provider_bonus)
        for name, value in base.items()
    }


@contextmanager
def _configured(provider: str, retrieval: str, backend: str) -> Iterator[None]:
    original = {
        "provider": settings.llm.provider,
        "default_provider": settings.llm_providers.default_provider,
        "retrieval_mode": settings.retrieval_mode,
        "structured": settings.structured_generation_enabled,
        "refine": settings.refine_max_iterations,
    }
    settings.llm.provider = provider
    settings.llm_providers.default_provider = provider
    settings.retrieval_mode = retrieval
    settings.structured_generation_enabled = backend != "baseline"
    settings.refine_max_iterations = 2 if backend == "refine" else 0
    try:
        yield
    finally:
        settings.llm.provider = original["provider"]
        settings.llm_providers.default_provider = original["default_provider"]
        settings.retrieval_mode = original["retrieval_mode"]
        settings.structured_generation_enabled = original["structured"]
        settings.refine_max_iterations = original["refine"]


@contextmanager
def _dataset_subset(dataset: str, n_cases: int | None) -> Iterator[str]:
    if not n_cases or n_cases <= 0:
        yield dataset
        return
    cases = load_dataset(dataset)[:n_cases]
    with TemporaryDirectory(prefix="jikai-eval-") as tmp:
        path = Path(tmp) / "subset.jsonl"
        path.write_text(
            "\n".join(case.model_dump_json() for case in cases) + "\n",
            encoding="utf-8",
        )
        yield str(path)


async def _run_real(
    *,
    provider: str,
    retrieval: str,
    backend: str,
    dataset: str,
    n_cases: int | None,
    max_concurrency: int,
) -> dict[str, Any]:
    with (
        _configured(provider, retrieval, backend),
        _dataset_subset(dataset, n_cases) as ds,
    ):
        report = await run_eval(
            EvalRequest(
                workflow="jikai_eval_v1",
                dataset=ds,
                evaluators=METRICS,
                max_concurrency=max_concurrency,
                batch_id=f"{provider}-{retrieval}-{backend}",
            )
        )
    return {
        "provider": provider,
        "retrieval": retrieval,
        "backend": backend,
        "n_cases": report.summary.total_cases,
        "metrics": {
            metric: float(report.summary.evaluator_means.get(metric, 0.0))
            for metric in METRICS
        },
    }


def _leaderboard(results: dict[str, Any]) -> str:
    rows = sorted(
        results["runs"],
        key=lambda row: row["metrics"].get("ragas_faithfulness", 0.0),
        reverse=True,
    )
    lines = [
        "# Jikai Eval Leaderboard",
        "",
        "| Provider | Retrieval | Backend | R@5 | MRR | Faithfulness | Citation | IRAC | Hallucination |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        metrics = row["metrics"]
        lines.append(
            "| {provider} | {retrieval} | {backend} | {r:.3f} | {mrr:.3f} | {faith:.3f} | {cite:.3f} | {irac:.3f} | {hall:.3f} |".format(
                provider=row["provider"],
                retrieval=row["retrieval"],
                backend=row["backend"],
                r=metrics.get("retrieval_recall_at_k", 0.0),
                mrr=metrics.get("retrieval_mrr", 0.0),
                faith=metrics.get("ragas_faithfulness", 0.0),
                cite=metrics.get("citation_accuracy", 0.0),
                irac=metrics.get("irac_completeness", 0.0),
                hall=metrics.get("hallucination_profile", 0.0),
            )
        )
    return "\n".join(lines) + "\n"


async def build_results(args: argparse.Namespace) -> dict[str, Any]:
    providers = _split(args.providers)
    retrieval_modes = _split(args.retrieval)
    backends = _split(args.backends)
    case_count = len(load_dataset(args.dataset))
    if args.n_cases and args.n_cases > 0:
        case_count = min(case_count, args.n_cases)
    runs: list[dict[str, Any]] = []
    for provider in providers:
        for retrieval in retrieval_modes:
            for backend in backends:
                if args.dry_run:
                    runs.append(
                        {
                            "provider": provider,
                            "retrieval": retrieval,
                            "backend": backend,
                            "n_cases": case_count,
                            "metrics": _dry_metrics(provider, retrieval, backend),
                        }
                    )
                    continue
                runs.append(
                    await _run_real(
                        provider=provider,
                        retrieval=retrieval,
                        backend=backend,
                        dataset=args.dataset,
                        n_cases=args.n_cases,
                        max_concurrency=args.max_concurrency,
                    )
                )
    return {
        "schema_version": "jikai.results.v1",
        "generated_at": _now(),
        "corpus_pack": args.corpus_pack,
        "eval_dataset": args.dataset,
        "dry_run": bool(args.dry_run),
        "runs": runs,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Jikai eval sweeps")
    parser.add_argument("--providers", default="ollama,openai,anthropic")
    parser.add_argument("--retrieval", default="hybrid,dense,bm25")
    parser.add_argument("--backends", default="baseline,structured,refine")
    parser.add_argument("--dataset", default="corpus/eval/sg_tort_v1.jsonl")
    parser.add_argument("--corpus-pack", default="sg_tort")
    parser.add_argument(
        "--output", type=Path, default=Path("docs/evals/results_v1.json")
    )
    parser.add_argument("--n-cases", type=int)
    parser.add_argument("--max-concurrency", type=int, default=1)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    results = asyncio.run(build_results(args))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    leaderboard_path = args.output.parent / "leaderboard.md"
    leaderboard_path.write_text(_leaderboard(results), encoding="utf-8")
    print(f"wrote {args.output}")
    print(f"wrote {leaderboard_path}")


if __name__ == "__main__":
    main()
