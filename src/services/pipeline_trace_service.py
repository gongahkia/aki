"""Pipeline trace assembly for generation diagnostics."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import structlog

from ..domain import canonicalize_topic, resolve_domain_pack
from .corpus_service import (
    CorpusQuery,
    CorpusService,
    HypotheticalEntry,
    corpus_service,
)
from .hypothetical_service import GenerationRequest
from .prompt_engineering import PromptContext, PromptTemplateManager, PromptTemplateType
from .validation_service import ValidationService, validation_service
from .workflow_facade import WorkflowFacade, workflow_facade

logger = structlog.get_logger(__name__)

DEFAULT_TRACE_HYPOTHETICAL = (
    "Tan Wei Ming is a delivery rider in Singapore. Bright Services Pte Ltd asks him "
    "to use a company e-bike after several riders report that its brake lever sticks. "
    "Lim Shu Fen, a pedestrian at Marina Bay, is crossing a service road when the "
    "e-bike fails to slow down. Tan swerves, clips Lim, and knocks her into a loading "
    "barrier. The maintenance supervisor had postponed repairs to meet a holiday "
    "delivery target. The facts raise whether Bright Services owed and breached a "
    "duty of care, whether Tan acted reasonably in the emergency, and whether the "
    "brake defect caused Lim's physical injury and consequential loss."
)

DEFAULT_TRACE_MODEL_ANSWER = (
    "A strong answer would identify a duty of care owed by Bright Services and Tan "
    "to road users near the delivery route. Bright Services likely breached that "
    "duty by continuing to deploy an e-bike with a known brake defect after reports "
    "from other riders. Causation turns on whether the unrepaired brake materially "
    "contributed to the collision and Lim's injury. Tan's emergency swerve may reduce "
    "criticism of his conduct, but it does not necessarily break the causal chain."
)


class PipelineTraceService:
    """Build inspectable stage-by-stage generation traces."""

    def __init__(
        self,
        *,
        corpus: CorpusService = corpus_service,
        validator: ValidationService = validation_service,
        workflow: WorkflowFacade = workflow_facade,
        prompt_manager: Optional[PromptTemplateManager] = None,
    ):
        self._corpus = corpus
        self._validator = validator
        self._workflow = workflow
        self._prompt_manager = prompt_manager or PromptTemplateManager()

    async def build_trace(
        self,
        request: GenerationRequest,
        *,
        live: bool = False,
        expose_prompt: bool = False,
        expose_provider: bool = False,
    ) -> Dict[str, Any]:
        """Return one end-to-end generation trace."""
        retrieved = await self._retrieve_cases(request)
        prompt_snapshot = self._prompt_snapshot(
            request, retrieved, expose_prompt=expose_prompt
        )
        generation = await self._generation_snapshot(
            request,
            live=live,
            retrieved=retrieved,
            expose_provider=expose_provider,
        )
        validation_snapshot = self._validation_snapshot(
            request,
            generation["output"],
            retrieved,
            provided_validation=generation.get("validation_results"),
        )
        ml_snapshot = self._ml_snapshot(
            request,
            generation["output"],
            validation_snapshot,
            generation.get("ml_foundation", {}),
            retrieved,
        )

        stages = [
            self._stage("input", "Input", "complete", self._input_snapshot(request)),
            self._stage(
                "classification",
                "Classification",
                ml_snapshot["classification"]["status"],
                ml_snapshot["classification"],
            ),
            self._stage(
                "scoring",
                "Regression scoring",
                ml_snapshot["scoring"]["status"],
                ml_snapshot["scoring"],
            ),
            self._stage(
                "planning",
                "Clustering and topic planning",
                ml_snapshot["planning"]["status"],
                ml_snapshot["planning"],
            ),
            self._stage(
                "retrieval",
                "Retrieved cases",
                "complete" if retrieved else "warning",
                {"items": [self._entry_snapshot(entry) for entry in retrieved]},
            ),
            self._stage(
                "prompt",
                "Prompt assembly",
                prompt_snapshot["status"],
                prompt_snapshot,
            ),
            self._stage(
                "generation",
                "Generated output",
                generation["status"],
                generation,
            ),
            self._stage(
                "validation",
                "Validation",
                "complete" if validation_snapshot["passed"] else "warning",
                validation_snapshot,
            ),
            self._stage(
                "study",
                "Study export",
                "complete",
                self._study_snapshot(request, generation["output"]),
            ),
        ]

        return {
            "schema_version": "1.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "mode": "live" if live else "fixture",
            "redaction": {
                "prompt_exposed": expose_prompt,
                "provider_exposed": expose_provider,
            },
            "summary": {
                "passed": validation_snapshot["passed"],
                "topics": request.topics,
                "jurisdiction": request.jurisdiction,
                "corpus_pack": request.corpus_pack,
                "retrieved_count": len(retrieved),
                "study_artifacts": ["model_answer", "anki_tsv"],
                "failure_reasons": validation_snapshot["failure_reasons"],
            },
            "stages": stages,
        }

    @staticmethod
    def _stage(
        stage_id: str, label: str, status: str, details: Dict[str, Any]
    ) -> Dict[str, Any]:
        return {
            "id": stage_id,
            "label": label,
            "status": status,
            "details": details,
        }

    @staticmethod
    def _input_snapshot(request: GenerationRequest) -> Dict[str, Any]:
        return {
            "topics": request.topics,
            "subtopics": request.subtopics,
            "corpus_pack": request.corpus_pack,
            "jurisdiction": request.jurisdiction,
            "subject": request.subject,
            "number_parties": request.number_parties,
            "complexity_level": request.complexity_level,
            "sample_size": request.sample_size,
        }

    async def _retrieve_cases(
        self, request: GenerationRequest
    ) -> List[HypotheticalEntry]:
        query = CorpusQuery(
            topics=request.topics,
            corpus_pack=request.corpus_pack,
            jurisdiction=request.jurisdiction,
            subject=request.subject,
            subtopics=request.subtopics,
            sample_size=request.sample_size,
            min_topic_overlap=1,
        )
        try:
            corpus = await self._corpus.load_corpus(corpus_pack=query.corpus_pack)
        except Exception as exc:
            logger.warning("pipeline trace corpus load failed", error=str(exc))
            return []

        scored = []
        for entry in corpus:
            if entry.corpus_pack_key != query.corpus_pack:
                continue
            if entry.jurisdiction != query.jurisdiction:
                continue
            if entry.subject != query.subject:
                continue
            overlap = len(set(entry.topics) & set(query.topics))
            if overlap >= query.min_topic_overlap:
                scored.append((entry, overlap))
        scored.sort(key=lambda item: item[1], reverse=True)
        return [entry for entry, _score in scored[: query.sample_size]]

    def _entry_snapshot(self, entry: HypotheticalEntry) -> Dict[str, Any]:
        source = entry.metadata.get("source", {})
        if not isinstance(source, dict):
            source = {}
        return {
            "id": entry.id,
            "topics": entry.topics,
            "subtopics": entry.subtopics,
            "jurisdiction": entry.jurisdiction,
            "source": source.get("name") or entry.metadata.get("source_name") or "",
            "case_name": entry.metadata.get("case_name")
            or entry.metadata.get("case_abbreviation")
            or entry.metadata.get("title")
            or "",
            "excerpt": self._clip(entry.text, 220),
        }

    def _prompt_snapshot(
        self,
        request: GenerationRequest,
        retrieved: List[HypotheticalEntry],
        *,
        expose_prompt: bool,
    ) -> Dict[str, Any]:
        context = PromptContext(
            topics=request.topics,
            corpus_pack=request.corpus_pack,
            jurisdiction=request.jurisdiction,
            subject=request.subject,
            subtopics=request.subtopics,
            law_domain=request.law_domain,
            number_parties=request.number_parties,
            reference_hypotheticals=[entry.text for entry in retrieved],
            user_preferences=request.user_preferences,
            complexity_level=request.complexity_level,
        )
        prompt_data = self._prompt_manager.format_prompt(
            PromptTemplateType.HYPOTHETICAL_GENERATION, context
        )
        user_prompt = prompt_data.get("user", "")
        system_prompt = prompt_data.get("system", "")
        snapshot = {
            "status": "complete",
            "template": PromptTemplateType.HYPOTHETICAL_GENERATION.value,
            "reference_count": len(retrieved),
            "system_prompt_chars": len(system_prompt),
            "user_prompt_chars": len(user_prompt),
            "redacted": not expose_prompt,
        }
        if expose_prompt:
            snapshot["system_prompt"] = system_prompt
            snapshot["user_prompt"] = user_prompt
        else:
            snapshot["preview"] = self._clip(user_prompt, 320)
        return snapshot

    async def _generation_snapshot(
        self,
        request: GenerationRequest,
        *,
        live: bool,
        retrieved: List[HypotheticalEntry],
        expose_provider: bool,
    ) -> Dict[str, Any]:
        if not live:
            return {
                "status": "complete",
                "source": "deterministic_fixture",
                "output": DEFAULT_TRACE_HYPOTHETICAL,
                "model_answer": DEFAULT_TRACE_MODEL_ANSWER,
                "output_chars": len(DEFAULT_TRACE_HYPOTHETICAL),
                "provider": "redacted",
                "validation_results": None,
                "ml_foundation": {
                    "topics": request.topics,
                    "quality_score": 0.82,
                    "is_diverse": True,
                    "generation_id": "trace-fixture",
                },
            }

        result = await self._workflow.generate_generation(
            request, correlation_id=request.correlation_id
        )
        response = result.response
        preferences = result.request.user_preferences or {}
        provider_data: Dict[str, Any] = {
            "provider": result.request.provider,
            "model": result.request.model,
        }
        return {
            "status": "complete",
            "source": "live_workflow",
            "output": response.hypothetical,
            "model_answer": response.model_answer,
            "output_chars": len(response.hypothetical),
            "provider": provider_data if expose_provider else "redacted",
            "metadata": response.metadata,
            "validation_results": response.validation_results,
            "ml_foundation": preferences.get("ml_foundation", {}),
            "retrieved_count_observed_before_generation": len(retrieved),
        }

    def _study_snapshot(
        self,
        request: GenerationRequest,
        generated_text: str,
    ) -> Dict[str, Any]:
        tags = " ".join(f"tort::{topic}" for topic in request.topics)
        front = self._clip(generated_text, 420)
        back = self._clip(DEFAULT_TRACE_MODEL_ANSWER, 420)
        return {
            "model_answer": DEFAULT_TRACE_MODEL_ANSWER,
            "anki_tsv_preview": f"{front}\t{back}\t{tags}",
            "export_formats": ["anki_tsv", "generation_report"],
            "tags": tags,
            "note": "Preview only; /jobs/export-anki writes the TSV export in normal use.",
        }

    def _ml_snapshot(
        self,
        request: GenerationRequest,
        generated_text: str,
        validation_snapshot: Dict[str, Any],
        ml_foundation: Dict[str, Any],
        retrieved: List[HypotheticalEntry],
    ) -> Dict[str, Any]:
        topic_check = validation_snapshot["checks"].get("topic_inclusion", {})
        found_topics = topic_check.get("topics_found") or ml_foundation.get("topics")
        if not found_topics:
            found_topics = request.topics
        quality = ml_foundation.get("quality_score")
        if quality is None:
            quality = round(
                float(validation_snapshot.get("overall_score", 0.0)) / 10, 2
            )
        retrieved_topics = sorted(
            {topic for entry in retrieved for topic in entry.topics}
        )
        cluster_seed = "-".join(request.topics or ["general"])
        return {
            "classification": {
                "status": "complete",
                "requested_topics": request.topics,
                "predicted_topics": found_topics,
                "confidence": ml_foundation.get("quality_score", quality),
                "source": "ml_foundation_metadata_or_validator",
            },
            "scoring": {
                "status": "complete",
                "quality_score": quality,
                "overall_validation_score": validation_snapshot.get("overall_score"),
                "legal_realism_score": validation_snapshot.get("legal_realism_score"),
                "exam_likeness_score": validation_snapshot.get("exam_likeness_score"),
                "output_chars": len(generated_text),
            },
            "planning": {
                "status": "complete",
                "cluster_id": ml_foundation.get("cluster_id", f"trace:{cluster_seed}"),
                "is_diverse": bool(ml_foundation.get("is_diverse", True)),
                "retrieved_topic_pool": retrieved_topics,
                "plan": [
                    "normalize corpus pack and topic aliases",
                    "rank local corpus examples by topic overlap",
                    "assemble jurisdiction prompt overlay",
                    "validate topic, party, realism, and similarity gates",
                ],
            },
        }

    def _validation_snapshot(
        self,
        request: GenerationRequest,
        text: str,
        retrieved: List[HypotheticalEntry],
        *,
        provided_validation: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        if provided_validation:
            adherence = dict(provided_validation.get("adherence_check", {}))
            similarity = dict(provided_validation.get("similarity_check", {}))
            passed = bool(provided_validation.get("passed", False))
            overall_score = provided_validation.get("quality_score", 0.0)
            legal_realism = provided_validation.get("legal_realism_score", 0.0)
            exam_likeness = provided_validation.get("exam_likeness_score", 0.0)
            checks = adherence.get("checks", {})
        else:
            adherence = self._validator.validate_hypothetical(
                text=text,
                required_topics=request.topics,
                expected_parties=request.number_parties,
                law_domain=request.law_domain,
                corpus_pack=request.corpus_pack,
                jurisdiction=request.jurisdiction,
                subject=request.subject,
                subtopics=request.subtopics,
                fast_mode=True,
            )
            similarity = self._similarity_snapshot(text, retrieved)
            passed = bool(adherence.get("passed")) and bool(similarity.get("passed"))
            overall_score = adherence.get("overall_score", 0.0)
            legal_realism = (
                adherence.get("checks", {})
                .get("legal_realism", {})
                .get("realism_score", 0.0)
            )
            exam_likeness = (
                adherence.get("checks", {})
                .get("exam_likeness", {})
                .get("exam_likeness_score", 0.0)
            )
            checks = adherence.get("checks", {})

        failure_reasons = self._validation_failure_reasons(
            adherence, similarity, passed=passed
        )
        return {
            "passed": passed,
            "overall_score": overall_score,
            "legal_realism_score": legal_realism,
            "exam_likeness_score": exam_likeness,
            "checks": checks,
            "similarity_check": similarity,
            "failure_reasons": failure_reasons,
        }

    @staticmethod
    def _similarity_snapshot(
        text: str, retrieved: List[HypotheticalEntry]
    ) -> Dict[str, Any]:
        if not retrieved:
            return {
                "passed": True,
                "max_similarity": 0.0,
                "message": "No retrieved examples available for similarity check",
            }
        text_words = set(text.lower().split())
        max_similarity = 0.0
        for entry in retrieved:
            entry_words = set(entry.text.lower().split())
            if not entry_words:
                continue
            overlap = len(text_words & entry_words) / max(
                1, len(text_words | entry_words)
            )
            max_similarity = max(max_similarity, overlap)
        return {
            "passed": max_similarity < 0.7,
            "max_similarity": round(max_similarity, 3),
            "message": (
                "Overlap below copy-risk threshold"
                if max_similarity < 0.7
                else "Generated text is too close to a retrieved example"
            ),
        }

    @staticmethod
    def _validation_failure_reasons(
        adherence: Dict[str, Any],
        similarity: Dict[str, Any],
        *,
        passed: bool,
    ) -> List[str]:
        reasons: List[str] = []
        checks = adherence.get("checks", {})
        for name, check in checks.items():
            if isinstance(check, dict) and not check.get("passed", True):
                reasons.append(str(check.get("message") or f"{name} failed"))
        quality_gate = adherence.get("quality_gate", {})
        for failed in quality_gate.get("failed_checks", []):
            reasons.append(f"{failed} quality gate failed")
        if similarity and not similarity.get("passed", True):
            reasons.append(str(similarity.get("message") or "similarity check failed"))
        if not passed and not reasons:
            reasons.append("validation failed without a specific check message")
        deduped = []
        for reason in reasons:
            if reason not in deduped:
                deduped.append(reason)
        return deduped

    @staticmethod
    def _clip(value: str, max_chars: int) -> str:
        text = " ".join(str(value or "").split())
        if len(text) <= max_chars:
            return text
        return f"{text[: max_chars - 3].rstrip()}..."


def default_pipeline_trace_request() -> GenerationRequest:
    pack = resolve_domain_pack("sg_tort")
    topics = ["negligence", "causation"]
    return GenerationRequest(
        topics=[canonicalize_topic(topic) for topic in topics],
        corpus_pack=pack.key,
        jurisdiction=pack.jurisdiction_key,
        subject=pack.subject_key,
        law_domain=pack.subject_key,
        subtopics=[],
        number_parties=3,
        complexity_level="intermediate",
        sample_size=3,
        user_preferences={"prioritize_latency": True},
        include_analysis=True,
    )


pipeline_trace_service = PipelineTraceService()
