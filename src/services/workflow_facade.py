"""Shared generation/report/regeneration orchestration for API and TUI surfaces."""

import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import structlog

from ..domain import canonicalize_topic
from .corpus_service import CorpusService, corpus_service
from .database_service import (
    DatabaseService,
    GenerationReport,
    database_service,
)
from .hypothetical_service import (
    GenerationRequest,
    GenerationResponse,
    HypotheticalService,
    hypothetical_service,
)
from .topic_guard import canonicalize_and_validate_topics

logger = structlog.get_logger(__name__)


class WorkflowFacadeError(Exception):
    """Raised when a workflow operation cannot be completed."""

    def __init__(self, message: str, status_code: int = 500):
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class GenerationExecutionResult:
    """Result of normalized generation request execution."""

    request: GenerationRequest
    response: GenerationResponse


@dataclass(frozen=True)
class RegenerationExecutionResult:
    """Result of regeneration from persisted generation data."""

    source_generation_id: int
    feedback_context: str
    request_data: Dict[str, Any]
    regenerated: GenerationResponse


class WorkflowFacade:
    """Shared orchestration layer to avoid API/TUI business-logic duplication."""

    def __init__(
        self,
        *,
        corpus_service: CorpusService = corpus_service,
        hypothetical_service: HypotheticalService = hypothetical_service,
        database_service: DatabaseService = database_service,
    ):
        self._corpus_service = corpus_service
        self._hypothetical_service = hypothetical_service
        self._database_service = database_service

    @staticmethod
    def _extract_validation_failure_reasons(response: Dict[str, Any]) -> List[str]:
        validation_results = response.get("validation_results") or {}
        if validation_results.get("passed", True):
            return []

        reasons: List[str] = []
        adherence = validation_results.get("adherence_check") or {}
        quality_gate = adherence.get("quality_gate") or {}
        failed_checks = quality_gate.get("failed_checks") or []
        for check_name in failed_checks:
            if check_name == "legal_realism":
                reasons.append("legal realism score below threshold")
            elif check_name == "quality_score":
                reasons.append("overall quality score below threshold")
            else:
                reasons.append(f"{check_name} gate failed")

        similarity_check = validation_results.get("similarity_check") or {}
        if similarity_check and not similarity_check.get("passed", True):
            reasons.append("similarity check failed")

        checks = adherence.get("checks") or {}
        for check_name, check_data in checks.items():
            if isinstance(check_data, dict) and not check_data.get("passed", True):
                reasons.append(f"{check_name} validation failed")

        if not reasons:
            reasons.append("validation failed without explicit reason code")

        # Preserve order while removing duplicates.
        seen = set()
        deduped: List[str] = []
        for reason in reasons:
            if reason in seen:
                continue
            seen.add(reason)
            deduped.append(reason)
        return deduped

    async def _validate_topics(
        self, topics: List[str]
    ) -> tuple[List[str], float, List[str]]:
        canonical_topics = canonicalize_and_validate_topics(topics)
        extraction_started = time.perf_counter()
        available_topics = [
            canonicalize_topic(topic)
            for topic in await self._corpus_service.extract_all_topics()
        ]
        extraction_time_ms = round((time.perf_counter() - extraction_started) * 1000, 2)
        return canonical_topics, extraction_time_ms, available_topics

    async def generate_generation(
        self,
        request: GenerationRequest,
        *,
        correlation_id: Optional[str] = None,
    ) -> GenerationExecutionResult:
        """Validate and execute a generation request."""
        canonical_topics, extraction_time_ms, available_topics = (
            await self._validate_topics(request.topics)
        )
        invalid_topics = [
            topic for topic in canonical_topics if topic not in available_topics
        ]
        if invalid_topics:
            raise WorkflowFacadeError(
                (
                    f"Invalid topics: {invalid_topics}. "
                    f"Available topics: {available_topics[:10]}..."
                ),
                status_code=400,
            )

        resolved_correlation_id = (
            correlation_id or request.correlation_id or str(uuid.uuid4())
        )
        prepared_request = request.model_copy(
            update={
                "topics": canonical_topics,
                "correlation_id": resolved_correlation_id,
                "topic_extraction_time_ms": extraction_time_ms,
            }
        )
        response = await self._hypothetical_service.generate_hypothetical(
            prepared_request
        )
        return GenerationExecutionResult(request=prepared_request, response=response)

    async def save_generation_report(
        self,
        *,
        generation_id: int,
        issue_types: List[str],
        comment: Optional[str],
        correlation_id: Optional[str] = None,
        is_locked: bool = True,
    ) -> int:
        """Persist an immutable report row for a generation."""
        if generation_id <= 0:
            raise WorkflowFacadeError("generation_id must be positive", status_code=400)

        report = GenerationReport(
            generation_id=generation_id,
            issue_types=issue_types,
            comment=comment,
            correlation_id=correlation_id,
            is_locked=is_locked,
        )
        try:
            return await self._database_service.save_generation_report(report)
        except Exception as exc:
            if "FOREIGN KEY constraint failed" in str(exc):
                raise WorkflowFacadeError(
                    f"Generation ID {generation_id} not found", status_code=404
                ) from exc
            logger.error("Failed to save generation report", error=str(exc))
            raise WorkflowFacadeError(
                "Failed to save generation report",
                status_code=500,
            ) from exc

    async def list_generation_reports(self, generation_id: int):
        """List saved reports for a generation id."""
        if generation_id <= 0:
            raise WorkflowFacadeError("generation_id must be positive", status_code=400)
        return await self._database_service.get_generation_reports(generation_id)

    async def regenerate_generation(
        self,
        *,
        generation_id: int,
        correlation_id: Optional[str] = None,
        fallback_request: Optional[Dict[str, Any]] = None,
    ) -> RegenerationExecutionResult:
        """Regenerate from persisted generation and latest report feedback."""
        if generation_id <= 0:
            raise WorkflowFacadeError("generation_id must be positive", status_code=400)

        row = await self._database_service.get_generation_by_id(generation_id)
        if not row:
            raise WorkflowFacadeError(
                f"Generation ID {generation_id} not found",
                status_code=404,
            )

        fallback = fallback_request or {}
        request_data = dict(row.get("request", {}))
        original_topics = request_data.get("topics") or fallback.get("topics") or []
        if not original_topics:
            raise WorkflowFacadeError(
                f"Generation ID {generation_id} has no stored topics to regenerate",
                status_code=400,
            )

        canonical_topics = canonicalize_and_validate_topics(original_topics)
        feedback_context = (
            await self._database_service.build_regeneration_feedback_context(
                generation_id
            )
        )
        validation_failure_reasons = self._extract_validation_failure_reasons(
            dict(row.get("response") or {})
        )
        if validation_failure_reasons:
            reason_context = "Validation failures: " + "; ".join(validation_failure_reasons)
            feedback_context = (
                f"{feedback_context} | {reason_context}".strip(" |")
                if feedback_context
                else reason_context
            )
        reports = await self._database_service.get_generation_reports(generation_id)
        latest_report = reports[-1] if reports else None

        retry_reason = "report_feedback"
        if latest_report and latest_report.issue_types:
            retry_reason = "report_feedback:" + ",".join(latest_report.issue_types[:3])

        raw_retry_attempt = request_data.get(
            "retry_attempt",
            row.get("retry_attempt", fallback.get("retry_attempt", 0)),
        )
        try:
            retry_attempt = max(1, int(raw_retry_attempt) + 1)
        except (TypeError, ValueError):
            retry_attempt = 1

        user_preferences = dict(request_data.get("user_preferences") or {})
        fallback_preferences = dict(fallback.get("user_preferences") or {})
        for key, value in fallback_preferences.items():
            user_preferences.setdefault(key, value)

        if feedback_context:
            existing_feedback = str(user_preferences.get("feedback", "")).strip()
            user_preferences["feedback"] = (
                f"{existing_feedback} {feedback_context}".strip()
                if existing_feedback
                else feedback_context
            )

        regenerate_request = GenerationRequest(
            topics=canonical_topics,
            law_domain=request_data.get(
                "law_domain", fallback.get("law_domain", "tort")
            ),
            number_parties=request_data.get(
                "number_parties", fallback.get("number_parties", 3)
            ),
            complexity_level=request_data.get(
                "complexity_level", fallback.get("complexity_level", "intermediate")
            ),
            sample_size=request_data.get("sample_size", fallback.get("sample_size", 3)),
            user_preferences=user_preferences,
            method=request_data.get("method", fallback.get("method", "pure_llm")),
            provider=request_data.get("provider", fallback.get("provider")),
            model=request_data.get("model", fallback.get("model")),
            include_analysis=bool(
                request_data.get(
                    "include_analysis", fallback.get("include_analysis", True)
                )
            ),
            parent_generation_id=generation_id,
            retry_reason=retry_reason,
            retry_attempt=retry_attempt,
            correlation_id=correlation_id or str(uuid.uuid4()),
        )

        regenerated = await self._hypothetical_service.generate_hypothetical(
            regenerate_request
        )
        return RegenerationExecutionResult(
            source_generation_id=generation_id,
            feedback_context=feedback_context,
            request_data=request_data,
            regenerated=regenerated,
        )


workflow_facade = WorkflowFacade()
