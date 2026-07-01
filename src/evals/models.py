"""Stable models for local SG-LegalBench eval runs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator


class EvalCase(BaseModel):
    name: str
    inputs: dict[str, Any]
    expected_output: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def require_jurisdiction(self) -> "EvalCase":
        if "jurisdiction" not in self.metadata:
            raise ValueError("case.metadata.jurisdiction is required")
        return self


class EvalRequest(BaseModel):
    workflow: str
    dataset: str
    evaluators: list[str] = Field(default_factory=lambda: ["contains"])
    max_concurrency: int = Field(default=5, ge=1, le=50)
    batch_id: str | None = None


class EvaluatorResult(BaseModel):
    name: str
    score: float = Field(ge=0.0, le=1.0)
    passed: bool
    details: dict[str, Any] = Field(default_factory=dict)


class EvalCaseResult(BaseModel):
    name: str
    output: str
    metadata: dict[str, Any]
    expected_output: dict[str, Any]
    evaluator_results: list[EvaluatorResult]
    score: float = Field(ge=0.0, le=1.0)
    passed: bool
    duration_seconds: float
    error: str | None = None


class EvalSummary(BaseModel):
    total_cases: int
    passed_cases: int
    failed_cases: int
    mean_score: float = Field(ge=0.0, le=1.0)
    evaluator_means: dict[str, float]


class EvalReport(BaseModel):
    schema_version: str = "jikai.eval.v1"
    workflow: str
    dataset: str
    batch_id: str
    evaluators: list[str]
    max_concurrency: int
    started_at: str
    finished_at: str
    duration_seconds: float
    summary: EvalSummary
    cases: list[EvalCaseResult]

    def print(self) -> None:
        import builtins

        builtins.print(
            f"{self.workflow} on {self.dataset}: "
            f"{self.summary.passed_cases}/{self.summary.total_cases} passed, "
            f"mean={self.summary.mean_score:.3f}, batch={self.batch_id}"
        )
