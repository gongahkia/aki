#!/usr/bin/env python3
"""Run Jikai backend ablations and emit JSON/markdown artifacts."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from run_jikai_eval import METRICS, _dataset_subset, _metric, _now  # noqa: E402
from src.config import settings  # noqa: E402
from src.evals import EvalRequest, run_eval  # noqa: E402
from src.evals.runner import load_dataset  # noqa: E402

SCENARIOS = {
    "baseline": {"structured": False, "refine": 0, "setfit": False},
    "+structured": {"structured": True, "refine": 0, "setfit": False},
    "+refine": {"structured": True, "refine": 2, "setfit": False},
    "+setfit": {"structured": False, "refine": 0, "setfit": True},
    "+all": {"structured": True, "refine": 2, "setfit": True},
}


@contextmanager
def _configured(
    *, provider: str, retrieval: str, structured: bool, refine: int, setfit: bool
) -> Iterator[None]:
    original = {
        "provider": settings.llm.provider,
        "default_provider": settings.llm_providers.default_provider,
        "retrieval_mode": settings.retrieval_mode,
        "structured": settings.structured_generation_enabled,
        "refine": settings.refine_max_iterations,
        "ml_gate": settings.ml_gate_blocking,
    }
    settings.llm.provider = provider
    settings.llm_providers.default_provider = provider
    settings.retrieval_mode = retrieval
    settings.structured_generation_enabled = structured
    settings.refine_max_iterations = refine
    settings.ml_gate_blocking = setfit
    try:
        yield
    finally:
        settings.llm.provider = original["provider"]
        settings.llm_providers.default_provider = original["default_provider"]
        settings.retrieval_mode = original["retrieval_mode"]
        settings.structured_generation_enabled = original["structured"]
        settings.refine_max_iterations = original["refine"]
        settings.ml_gate_blocking = original["ml_gate"]


def _dry_metrics(name: str) -> dict[str, float]:
    base = {
        "retrieval_recall_at_k": 0.58,
        "retrieval_mrr": 0.46,
        "retrieval_ndcg": 0.5,
        "ragas_faithfulness": 0.62,
        "citation_accuracy": 0.57,
        "hallucination_profile": 0.66,
        "irac_completeness": 0.54,
    }
    bonus = {
        "baseline": 0.0,
        "+structured": 0.06,
        "+refine": 0.11,
        "+setfit": 0.05,
        "+all": 0.16,
    }[name]
    return {metric: _metric(value + bonus) for metric, value in base.items()}


async def _run_real(args: argparse.Namespace, name: str) -> dict[str, float]:
    config = SCENARIOS[name]
    with (
        _configured(
            provider=args.provider,
            retrieval=args.retrieval,
            structured=bool(config["structured"]),
            refine=int(config["refine"]),
            setfit=bool(config["setfit"]),
        ),
        _dataset_subset(args.dataset, args.n_cases) as dataset,
    ):
        report = await run_eval(
            EvalRequest(
                workflow="jikai_eval_v1",
                dataset=dataset,
                evaluators=METRICS,
                max_concurrency=args.max_concurrency,
                batch_id=f"ablation-{name}",
            )
        )
    return {
        metric: float(report.summary.evaluator_means.get(metric, 0.0))
        for metric in METRICS
    }


def _with_delta(
    name: str, metrics: dict[str, float], baseline: dict[str, float]
) -> dict[str, Any]:
    return {
        "name": name,
        "metrics": metrics,
        "delta_vs_baseline": {
            metric: round(metrics.get(metric, 0.0) - baseline.get(metric, 0.0), 6)
            for metric in METRICS
        },
    }


def _markdown(results: dict[str, Any]) -> str:
    lines = [
        "# Jikai Ablations",
        "",
        "| Scenario | Faithfulness | Citation | IRAC | Hallucination | Delta Faithfulness |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in results["scenarios"]:
        metrics = row["metrics"]
        delta = row["delta_vs_baseline"]
        lines.append(
            "| {name} | {faith:.3f} | {cite:.3f} | {irac:.3f} | {hall:.3f} | {df:+.3f} |".format(
                name=row["name"],
                faith=metrics.get("ragas_faithfulness", 0.0),
                cite=metrics.get("citation_accuracy", 0.0),
                irac=metrics.get("irac_completeness", 0.0),
                hall=metrics.get("hallucination_profile", 0.0),
                df=delta.get("ragas_faithfulness", 0.0),
            )
        )
    return "\n".join(lines) + "\n"


async def build_ablations(args: argparse.Namespace) -> dict[str, Any]:
    case_count = len(load_dataset(args.dataset))
    if args.n_cases and args.n_cases > 0:
        case_count = min(case_count, args.n_cases)
    raw: dict[str, dict[str, float]] = {}
    for name in SCENARIOS:
        raw[name] = _dry_metrics(name) if args.dry_run else await _run_real(args, name)
    baseline = raw["baseline"]
    return {
        "schema_version": "jikai.ablations.v1",
        "generated_at": _now(),
        "provider": args.provider,
        "retrieval": args.retrieval,
        "eval_dataset": args.dataset,
        "n_cases": case_count,
        "dry_run": bool(args.dry_run),
        "scenarios": [_with_delta(name, raw[name], baseline) for name in SCENARIOS],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Jikai eval ablations")
    parser.add_argument("--provider", default="ollama")
    parser.add_argument("--retrieval", default="hybrid")
    parser.add_argument("--dataset", default="corpus/eval/sg_tort_v1.jsonl")
    parser.add_argument(
        "--output", type=Path, default=Path("docs/evals/ablations_v1.json")
    )
    parser.add_argument("--n-cases", type=int)
    parser.add_argument("--max-concurrency", type=int, default=1)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    results = asyncio.run(build_ablations(args))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    markdown_path = args.output.parent / "ablations.md"
    markdown_path.write_text(_markdown(results), encoding="utf-8")
    print(f"wrote {args.output}")
    print(f"wrote {markdown_path}")


if __name__ == "__main__":
    main()
