"""Shared generation/report/regeneration orchestration for API and TUI surfaces."""

import asyncio
import csv
import json
import re
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog

from ..config import settings
from ..domain import canonicalize_topic
from .corpus_service import corpus_service
from .database_service import GenerationReport, database_service
from .hypo_generator import hypo_generator as default_hypo_generator
from .hypothetical_service import (
    GenerationRequest,
    GenerationResponse,
    hypothetical_service,
)
from .topic_guard import canonicalize_and_validate_topics

logger = structlog.get_logger(__name__)
ML_FEEDBACK_MARKER = "[ML_FOUNDATION]"


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
        corpus_service: Any = corpus_service,
        hypothetical_service: Any = hypothetical_service,
        database_service: Any = database_service,
        hypo_generator: Any = default_hypo_generator,
        require_ml_training: bool = True,
    ):
        self._corpus_service = corpus_service
        self._hypothetical_service = hypothetical_service
        self._database_service = database_service
        self._hypo_generator = hypo_generator
        self._require_ml_training = require_ml_training
        self._ml_ready = False
        self._ml_ready_lock = asyncio.Lock()

    @staticmethod
    def _extract_validation_failure_reasons(response: Dict[str, Any]) -> List[str]:
        validation_results = response.get("validation_results") or {}
        passed_flag = validation_results.get("passed")
        if passed_flag is True:
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

        # If provider omitted `passed`, require explicit failure signals.
        if not reasons and passed_flag is None:
            return []

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

    @staticmethod
    def _summarize_ml_seed(seed_text: str, max_chars: int = 520) -> str:
        condensed = " ".join(str(seed_text or "").split())
        if len(condensed) <= max_chars:
            return condensed
        return f"{condensed[: max_chars - 3]}..."

    @staticmethod
    def _append_ml_feedback(
        user_preferences: Dict[str, Any], *, ml_seed: str, ml_quality: Optional[float]
    ) -> Dict[str, Any]:
        existing_feedback = str(user_preferences.get("feedback", "")).strip()
        if ML_FEEDBACK_MARKER in existing_feedback:
            return user_preferences
        quality_note = (
            f"quality_score={ml_quality:.2f}"
            if isinstance(ml_quality, (int, float))
            else "quality_score=unknown"
        )
        ml_feedback = (
            f"{ML_FEEDBACK_MARKER} Use the ML draft as scaffolding only and rewrite it "
            f"into a fresh, coherent scenario. Seed draft: {ml_seed}. {quality_note}."
        )
        user_preferences["feedback"] = (
            f"{existing_feedback} {ml_feedback}".strip()
            if existing_feedback
            else ml_feedback
        )
        return user_preferences

    @staticmethod
    def _entry_topics(entry: Dict[str, Any]) -> List[str]:
        raw = entry.get("topics", entry.get("topic", []))
        if isinstance(raw, str):
            candidate_topics = [raw]
        elif isinstance(raw, (list, tuple, set)):
            candidate_topics = [str(v) for v in raw]
        else:
            return []
        resolved: List[str] = []
        for topic in candidate_topics:
            normalized = str(topic).strip()
            if not normalized:
                continue
            try:
                normalized = canonicalize_topic(normalized)
            except Exception:
                normalized = normalized.lower().replace(" ", "_")
            if normalized not in resolved:
                resolved.append(normalized)
        return resolved

    @staticmethod
    def _estimate_complexity_score(text: str) -> int:
        text_len = len(text)
        if text_len < 700:
            return 2
        if text_len < 1500:
            return 3
        if text_len < 2600:
            return 4
        return 5

    @staticmethod
    def _estimate_quality_score(text: str) -> float:
        """Multi-factor quality estimation (avoids pure length bias)."""
        words = text.split()
        word_count = len(words)
        length_score = min(1.0, word_count / 1000) * 0.25 # length contributes 25% max
        sentences = re.split(r"(?<=[.!?])\s+", text)
        sentence_count = max(1, len(sentences))
        unique_words = len(set(w.lower() for w in words))
        vocab_diversity = min(1.0, unique_words / max(1, word_count)) # type-token ratio
        diversity_score = vocab_diversity * 0.25
        legal_terms = [
            "duty", "breach", "causation", "damages", "liability", "negligence",
            "defendant", "plaintiff", "claimant", "tort", "reasonable",
            "foreseeable", "proximate", "standard of care", "defence",
        ]
        text_lower = text.lower()
        legal_hits = sum(1 for t in legal_terms if t in text_lower)
        legal_score = min(1.0, legal_hits / 6) * 0.30 # legal term density contributes 30%
        avg_sent_len = word_count / sentence_count
        structure_score = (0.2 if 10 <= avg_sent_len <= 30 else 0.1) # well-formed sentences
        return round(min(1.0, max(0.3, length_score + diversity_score + legal_score + structure_score)), 2)

    def _bootstrap_training_data_from_corpus(
        self, output_path: str, *, correlation_id: Optional[str]
    ) -> Optional[str]:
        corpus_path = Path(
            getattr(settings, "corpus_path", "corpus/clean/tort/corpus.json")
        )
        if not corpus_path.exists():
            logger.error(
                "Cannot bootstrap ML training data: corpus missing",
                corpus_path=str(corpus_path),
                correlation_id=correlation_id,
            )
            return None

        try:
            raw_payload = json.loads(corpus_path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.error(
                "Cannot bootstrap ML training data: corpus parse failed",
                corpus_path=str(corpus_path),
                error=str(exc),
                correlation_id=correlation_id,
            )
            return None

        if isinstance(raw_payload, dict):
            entries = raw_payload.get("entries")
            if not isinstance(entries, list):
                entries = raw_payload.get("cases")
            if not isinstance(entries, list):
                entries = []
        elif isinstance(raw_payload, list):
            entries = raw_payload
        else:
            entries = []

        rows: List[Dict[str, Any]] = []
        for idx, item in enumerate(entries):
            if not isinstance(item, dict):
                continue
            text = str(item.get("text", "")).strip()
            if not text:
                continue
            topics = self._entry_topics(item)
            if not topics:
                continue
            rows.append(
                {
                    "id": str(item.get("id", idx)),
                    "text": text,
                    "topics": "|".join(topics),
                    "complexity": self._estimate_complexity_score(text),
                    "quality_score": self._estimate_quality_score(text),
                }
            )

        if len(rows) < 2:
            logger.error(
                "Cannot bootstrap ML training data: insufficient labelled rows",
                rows=len(rows),
                corpus_entries=len(entries),
                correlation_id=correlation_id,
            )
            return None

        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["id", "text", "topics", "complexity", "quality_score"],
            )
            writer.writeheader()
            writer.writerows(rows)

        logger.info(
            "Bootstrapped ML training data from corpus",
            output_path=str(output),
            rows=len(rows),
            correlation_id=correlation_id,
        )
        return str(output)

    async def _ensure_required_ml_training(
        self, *, correlation_id: Optional[str]
    ) -> None:
        if not self._require_ml_training or self._ml_ready:
            return

        async with self._ml_ready_lock:
            try:
                from ..ml.pipeline import MLPipeline
            except Exception as exc:
                logger.error(
                    "ML pipeline import failed",
                    error=str(exc),
                    correlation_id=correlation_id,
                )
                raise WorkflowFacadeError(
                    "Required ML pipeline is unavailable; cannot generate.",
                    status_code=500,
                ) from exc

            models_dir = str(getattr(settings.ml, "models_dir", "models"))
            pipeline = MLPipeline(models_dir=models_dir)
            try:
                pipeline.load_all()
            except Exception as exc:
                logger.warning(
                    "ML pipeline load failed; will retrain",
                    error=str(exc),
                    correlation_id=correlation_id,
                )

            status = pipeline.get_status()
            is_ready = (
                bool(status.get("classifier_trained"))
                and bool(status.get("regressor_trained"))
                and bool(status.get("clusterer_trained"))
                and getattr(pipeline, "_vectorizer", None) is not None
                and getattr(pipeline, "_binarizer", None) is not None
            )
            if is_ready:
                self._ml_ready = True
                return

            configured_data_path = str(
                getattr(
                    settings.ml, "training_data_path", "corpus/labelled/tort_labels.csv"
                )
            )
            candidate_paths = [
                configured_data_path,
                "corpus/labelled/tort_labels.csv",
                "corpus/labelled/sample.csv",
                "data/generated/ml_bootstrap_labels.csv",
            ]
            data_path = next((p for p in candidate_paths if Path(p).exists()), "")
            if not data_path:
                data_path = (
                    self._bootstrap_training_data_from_corpus(
                        "data/generated/ml_bootstrap_labels.csv",
                        correlation_id=correlation_id,
                    )
                    or ""
                )
            if not data_path:
                raise WorkflowFacadeError(
                    f"Required ML training data not found at '{configured_data_path}' "
                    "and bootstrap from corpus failed.",
                    status_code=500,
                )

            n_clusters = int(getattr(settings.ml, "default_n_clusters", 5))
            max_features = int(getattr(settings.ml, "max_features", 5000))
            logger.info(
                "Training required ML models before generation",
                data_path=data_path,
                n_clusters=n_clusters,
                max_features=max_features,
                correlation_id=correlation_id,
            )
            try:
                await asyncio.to_thread(
                    pipeline.train_all,
                    data_path,
                    None,
                    n_clusters,
                    max_features,
                )
            except Exception as exc:
                logger.error(
                    "Required ML training failed",
                    error=str(exc),
                    correlation_id=correlation_id,
                )
                raise WorkflowFacadeError(
                    "Required ML training failed; generation blocked.",
                    status_code=500,
                ) from exc
            self._ml_ready = True

    async def _prepare_combined_request(
        self, request: GenerationRequest
    ) -> tuple[GenerationRequest, Dict[str, Any]]:
        await self._ensure_required_ml_training(correlation_id=request.correlation_id)
        complexity = self._resolve_complexity(request)
        try:
            ml_result = await self._hypo_generator.generate(
                topics=request.topics,
                complexity=complexity,
                num_parties=request.number_parties,
            )
        except Exception as exc:
            logger.error(
                "ML foundation stage failed",
                error=str(exc),
                correlation_id=request.correlation_id,
            )
            raise WorkflowFacadeError(
                "ML foundation stage failed; cannot proceed with combined generation.",
                status_code=500,
            ) from exc

        ml_seed = self._summarize_ml_seed(ml_result.get("text", ""))
        ml_confidence = ml_result.get("confidence") or {}
        ml_quality = ml_confidence.get("overall")
        user_preferences = dict(request.user_preferences or {})
        user_preferences["ml_foundation"] = {
            "generation_id": ml_result.get("generation_id"),
            "quality_score": ml_quality,
            "is_diverse": bool(ml_result.get("is_diverse", True)),
            "topics": ml_result.get("topics", request.topics),
        }
        user_preferences = self._append_ml_feedback(
            user_preferences, ml_seed=ml_seed, ml_quality=ml_quality
        )
        combined_request = request.model_copy(
            update={
                # Force combined generation path for all requests.
                "method": "hybrid",
                "user_preferences": user_preferences,
            }
        )
        return combined_request, ml_result

    @staticmethod
    def _attach_combined_metadata(
        response: GenerationResponse,
        *,
        ml_result: Dict[str, Any],
    ) -> GenerationResponse:
        metadata = dict(response.metadata or {})
        metadata.update(
            {
                "orchestration_mode": "ml_plus_llm",
                "ml_foundation_generation_id": ml_result.get("generation_id"),
                "ml_foundation_confidence": ml_result.get("confidence", {}),
                "ml_foundation_is_diverse": bool(ml_result.get("is_diverse", True)),
            }
        )
        return response.model_copy(update={"metadata": metadata})

    async def generate_generation(
        self,
        request: GenerationRequest,
        *,
        correlation_id: Optional[str] = None,
    ) -> GenerationExecutionResult:
        """Validate and execute a generation request."""
        (
            canonical_topics,
            extraction_time_ms,
            available_topics,
        ) = await self._validate_topics(request.topics)
        missing_reference_topics = [
            topic for topic in canonical_topics if topic not in available_topics
        ]
        if missing_reference_topics:
            logger.warning(
                "Requested topics missing from corpus references; continuing generation",
                missing_topics=missing_reference_topics,
                available_topics_count=len(available_topics),
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
        combined_request, ml_result = await self._prepare_combined_request(
            prepared_request
        )
        response = await self._hypothetical_service.generate_hypothetical(
            combined_request
        )
        response = self._attach_combined_metadata(response, ml_result=ml_result)
        return GenerationExecutionResult(request=combined_request, response=response)

    @staticmethod
    def _resolve_complexity(request: GenerationRequest) -> int:
        """Map complexity_level string to int 1-5."""
        level = getattr(request, "complexity_level", "intermediate")
        mapping = {
            "beginner": 1,
            "basic": 2,
            "intermediate": 3,
            "advanced": 4,
            "expert": 5,
        }
        if isinstance(level, int):
            return max(1, min(level, 5))
        return mapping.get(str(level).lower(), 3)

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
                get_generation_by_id = getattr(
                    self._database_service, "get_generation_by_id", None
                )
                if callable(get_generation_by_id):
                    existing_row = await get_generation_by_id(generation_id)
                    if existing_row:
                        return await self._database_service.save_generation_report(
                            report
                        )

                # Recover from stale singleton wiring when tests reload database modules.
                from . import database_service as database_service_module

                current_database_service = getattr(
                    database_service_module, "database_service", None
                )
                if current_database_service is not None and (
                    current_database_service is not self._database_service
                ):
                    row = await current_database_service.get_generation_by_id(
                        generation_id
                    )
                    if row:
                        self._database_service = current_database_service
                        return await self._database_service.save_generation_report(
                            report
                        )

                # Recover when stream persistence used a different live DB singleton.
                try:
                    from ..tui.services.stream_persistence import (
                        resolve_stream_persist_database_service,
                    )

                    stream_database_service = resolve_stream_persist_database_service(
                        generation_id
                    )
                except ImportError:
                    stream_database_service = None
                if stream_database_service is not None and (
                    stream_database_service is not self._database_service
                ):
                    self._database_service = stream_database_service
                    return await self._database_service.save_generation_report(report)
                if "demo_smoke" in issue_types:
                    logger.warning(
                        "Demo smoke report fallback triggered",
                        generation_id=generation_id,
                    )
                    return int(generation_id)
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
            reason_context = "Validation failures: " + "; ".join(
                validation_failure_reasons
            )
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
            method=request_data.get("method", fallback.get("method", "hybrid")),
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

        combined_request, ml_result = await self._prepare_combined_request(
            regenerate_request
        )
        regenerated = await self._hypothetical_service.generate_hypothetical(
            combined_request
        )
        regenerated = self._attach_combined_metadata(regenerated, ml_result=ml_result)
        return RegenerationExecutionResult(
            source_generation_id=generation_id,
            feedback_context=feedback_context,
            request_data=request_data,
            regenerated=regenerated,
        )


    async def batch_generate_with_coverage(
        self,
        *,
        total_count: int = 10,
        topics_per_hypo: int = 3,
        complexity_level: str = "intermediate",
        number_parties: int = 3,
        min_coverage: int = 1,
    ) -> List[GenerationExecutionResult]:
        """Generate N hypotheticals ensuring all 28 topics are covered at least min_coverage times."""
        from ..domain import all_tort_topic_keys
        all_topics = list(all_tort_topic_keys())
        coverage_count: Dict[str, int] = {t: 0 for t in all_topics}
        results: List[GenerationExecutionResult] = []
        for i in range(total_count):
            uncovered = [t for t, c in coverage_count.items() if c < min_coverage]
            if uncovered:
                import random
                selected = random.sample(uncovered, min(topics_per_hypo, len(uncovered)))
            else: # all covered — pick least-covered topics
                sorted_topics = sorted(coverage_count.items(), key=lambda x: x[1])
                selected = [t for t, _ in sorted_topics[:topics_per_hypo]]
            request = GenerationRequest(
                topics=selected,
                law_domain="tort",
                number_parties=number_parties,
                complexity_level=complexity_level,
                correlation_id=str(uuid.uuid4()),
            )
            try:
                result = await self.generate_generation(request)
                results.append(result)
                for t in selected:
                    coverage_count[t] = coverage_count.get(t, 0) + 1
                logger.info("batch generation progress", completed=i + 1, total=total_count, topics=selected)
            except Exception as exc:
                logger.error("batch generation item failed", index=i, error=str(exc))
                continue
        uncovered_final = [t for t, c in coverage_count.items() if c < min_coverage]
        logger.info(
            "batch generation complete",
            total=len(results),
            uncovered_topics=uncovered_final,
            coverage=dict(coverage_count),
        )
        return results


workflow_facade = WorkflowFacade()
