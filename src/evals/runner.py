"""Local eval runner with pydantic-evals-compatible dataset shape."""

from __future__ import annotations

import asyncio
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from .evaluators import EVALUATORS, EvaluatorContext
from .models import (
    EvalCase,
    EvalCaseResult,
    EvalReport,
    EvalRequest,
    EvalSummary,
    EvaluatorResult,
)
from .tasks import TASKS

DATASETS_DIR = Path(__file__).parent / "datasets"
CORPUS_EVAL_DIR = Path(__file__).resolve().parents[2] / "corpus" / "eval"


def resolve_dataset_path(dataset: str) -> Path:
    raw_path = Path(dataset)
    candidates = [raw_path]
    if not raw_path.suffix:
        candidates.append(raw_path.with_suffix(".yaml"))
        candidates.append(raw_path.with_suffix(".jsonl"))
    candidates.extend(
        [
            DATASETS_DIR / dataset,
            DATASETS_DIR / raw_path.with_suffix(".yaml").name,
            DATASETS_DIR / raw_path.with_suffix(".jsonl").name,
            CORPUS_EVAL_DIR / dataset,
            CORPUS_EVAL_DIR / raw_path.with_suffix(".yaml").name,
            CORPUS_EVAL_DIR / raw_path.with_suffix(".jsonl").name,
        ]
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"Eval dataset not found: {dataset}")


def load_dataset(dataset: str) -> list[EvalCase]:
    path = resolve_dataset_path(dataset)
    if path.suffix == ".jsonl":
        cases: list[EvalCase] = []
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                cases.append(EvalCase.model_validate(json.loads(line)))
        return cases
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    cases = payload.get("cases")
    if not isinstance(cases, list):
        raise ValueError("Eval dataset must contain a cases array")
    return [EvalCase.model_validate(case) for case in cases]


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _iso(ts: datetime) -> str:
    return ts.isoformat().replace("+00:00", "Z")


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


async def _run_case(
    case: EvalCase,
    *,
    workflow: str,
    evaluator_names: list[str],
    semaphore: asyncio.Semaphore,
) -> EvalCaseResult:
    started = time.perf_counter()
    output = ""
    error = None
    async with semaphore:
        try:
            output = await TASKS[workflow](case)
        except Exception as exc:
            error = str(exc)
        results: list[EvaluatorResult] = []
        context = EvaluatorContext(case=case, output=output)
        for name in evaluator_names:
            try:
                results.append(await EVALUATORS[name].evaluate(context))
            except Exception as exc:
                results.append(
                    EvaluatorResult(
                        name=name,
                        score=0.0,
                        passed=False,
                        details={"error": str(exc)},
                    )
                )
    score = _mean([result.score for result in results])
    return EvalCaseResult(
        name=case.name,
        output=output,
        metadata=case.metadata,
        expected_output=case.expected_output,
        evaluator_results=results,
        score=score,
        passed=error is None and all(result.passed for result in results),
        duration_seconds=round(time.perf_counter() - started, 6),
        error=error,
    )


def _summary(results: list[EvalCaseResult], evaluator_names: list[str]) -> EvalSummary:
    evaluator_means: dict[str, float] = {}
    for name in evaluator_names:
        scores = [
            result.score
            for case in results
            for result in case.evaluator_results
            if result.name == name
        ]
        evaluator_means[name] = round(_mean(scores), 6)
    return EvalSummary(
        total_cases=len(results),
        passed_cases=sum(1 for result in results if result.passed),
        failed_cases=sum(1 for result in results if not result.passed),
        mean_score=round(_mean([result.score for result in results]), 6),
        evaluator_means=evaluator_means,
    )


async def run_eval(req: EvalRequest) -> EvalReport:
    if req.workflow not in TASKS:
        raise ValueError(f"Unknown eval workflow: {req.workflow}")
    evaluator_names = req.evaluators or ["contains"]
    unknown = [name for name in evaluator_names if name not in EVALUATORS]
    if unknown:
        raise ValueError(f"Unknown evaluators: {unknown}")

    cases = load_dataset(req.dataset)
    started_at = _utc_now()
    batch_id = req.batch_id or f"{req.workflow}-{started_at:%Y%m%dT%H%M%SZ}"
    semaphore = asyncio.Semaphore(req.max_concurrency)
    results = await asyncio.gather(
        *[
            _run_case(
                case,
                workflow=req.workflow,
                evaluator_names=evaluator_names,
                semaphore=semaphore,
            )
            for case in cases
        ]
    )
    finished_at = _utc_now()
    return EvalReport(
        workflow=req.workflow,
        dataset=str(resolve_dataset_path(req.dataset)),
        batch_id=batch_id,
        evaluators=evaluator_names,
        max_concurrency=req.max_concurrency,
        started_at=_iso(started_at),
        finished_at=_iso(finished_at),
        duration_seconds=round((finished_at - started_at).total_seconds(), 6),
        summary=_summary(list(results), evaluator_names),
        cases=list(results),
    )


__all__ = ["DATASETS_DIR", "load_dataset", "resolve_dataset_path", "run_eval"]
