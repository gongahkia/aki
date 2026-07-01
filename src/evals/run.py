"""CLI entry point for SG-LegalBench evals."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
from typing import Any

from . import EvalRequest, run_eval
from .evaluators import EVALUATORS
from .tasks import TASKS


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Jikai SG-LegalBench evals")
    parser.add_argument("--workflow", required=True, choices=sorted(TASKS.keys()))
    parser.add_argument("--dataset", required=True)
    parser.add_argument(
        "--evaluator",
        action="append",
        default=[],
        choices=sorted(EVALUATORS.keys()),
    )
    parser.add_argument("--max-concurrency", type=int, default=5)
    parser.add_argument("--batch-id")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    evaluators = args.evaluator if args.evaluator else ["contains"]
    request = EvalRequest(
        workflow=args.workflow,
        dataset=args.dataset,
        evaluators=evaluators,
        max_concurrency=args.max_concurrency,
        batch_id=args.batch_id,
    )
    report: Any = asyncio.run(run_eval(request))
    report.print()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report.model_dump_json(indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
