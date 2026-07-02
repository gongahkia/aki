"""Bounded self-refine loop for generated hypotheticals."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable

import structlog

from ..config import settings
from .prompt_engineering.schemas import (
    CitationReport,
    FaithfulnessReport,
    RefineCritique,
)

logger = structlog.get_logger(__name__)


@dataclass
class RefineResult:
    hypothetical: str
    iterations: int
    final_critique: RefineCritique
    trace: list[dict[str, Any]]


class RefineLoop:
    def __init__(
        self,
        generate: Callable[[str], Awaitable[str]],
        rule_based_validate: Callable[[str], Awaitable[dict[str, Any]]],
        nli_verify: Callable[[str], Awaitable[FaithfulnessReport | None]] | None = None,
        citation_verify: (
            Callable[[str], Awaitable[CitationReport | None]] | None
        ) = None,
        ml_gate_check: Callable[[str], dict[str, Any]] | None = None,
        max_iterations: int | None = None,
        trace_path: Path | None = None,
    ) -> None:
        self.generate = generate
        self.rule_based_validate = rule_based_validate
        self.nli_verify = nli_verify
        self.citation_verify = citation_verify
        self.ml_gate_check = ml_gate_check
        self.max_iterations = (
            int(settings.refine_max_iterations)
            if max_iterations is None
            else int(max_iterations)
        )
        self.trace_path = trace_path

    async def run(
        self,
        initial_draft: str,
        revise_prompt_builder: Callable[[str, RefineCritique], str],
    ) -> RefineResult:
        trace: list[dict[str, Any]] = []
        current = initial_draft
        final_critique: RefineCritique | None = None
        for iteration in range(self.max_iterations + 1):
            rb = await self.rule_based_validate(current)
            faith = await self.nli_verify(current) if self.nli_verify else None
            cite = await self.citation_verify(current) if self.citation_verify else None
            gate = self.ml_gate_check(current) if self.ml_gate_check else {}
            critique = RefineCritique(
                iteration=iteration,
                missing_topics=list(rb.get("missing_topics", [])),
                ml_gate=gate,
                faithfulness=faith,
                citation=cite,
                rule_based=rb,
            )
            trace.append(
                {
                    "iteration": iteration,
                    "draft_prefix": current[:200],
                    "critique": critique.model_dump(),
                    "timestamp": time.time(),
                }
            )
            final_critique = critique
            if not critique.is_blocking() or iteration >= self.max_iterations:
                break
            current = await self.generate(revise_prompt_builder(current, critique))
        self._write_trace(trace)
        return RefineResult(
            hypothetical=current,
            iterations=max(0, len(trace) - 1),
            final_critique=final_critique or RefineCritique(iteration=0),
            trace=trace,
        )

    def _write_trace(self, trace: list[dict[str, Any]]) -> None:
        if not self.trace_path:
            return
        try:
            self.trace_path.parent.mkdir(parents=True, exist_ok=True)
            with self.trace_path.open("w", encoding="utf-8") as handle:
                for row in trace:
                    handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        except OSError as exc:
            logger.warning(
                "Refine trace write failed",
                trace_path=str(self.trace_path),
                error=str(exc),
            )


__all__ = ["RefineLoop", "RefineResult"]
