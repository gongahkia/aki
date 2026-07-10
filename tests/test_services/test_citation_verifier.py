"""Tests for citation verification."""

import importlib
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest

from src.config import settings
from src.services.hypothetical_service import (
    GenerationRequest,
    HypotheticalService,
    ValidationResult,
)
from src.services.prompt_engineering.schemas import (
    CitationReport,
    CorpusRef,
    IRACStep,
    ModelAnswer,
)
from src.services.verification.citation_verifier import (
    CitationVerifier,
    _issue_to_topic,
)


def _answer(
    *,
    issue: str = "Did the defendant owe a duty of care to the claimant?",
    citations: list[CorpusRef] | None = None,
) -> ModelAnswer:
    return ModelAnswer(
        steps=[
            IRACStep(
                issue=issue,
                rule="A defendant owes a duty where foreseeability and proximity are shown.",
                application=(
                    "The facts indicate a direct relationship between the defendant's "
                    "conduct and the claimant's injury."
                ),
                conclusion="A duty of care was likely owed on these facts.",
                citations=citations or [CorpusRef(corpus_id="c1")],
            )
        ],
        overall_conclusion="The claimant has a viable negligence claim against the defendant.",
    )


@pytest.mark.asyncio
async def test_verify_model_answer_accepts_matching_corpus_topic():
    verifier = CitationVerifier()
    verifier._corpus_indexes["sg_tort"] = {
        "c1": {"topics": {"duty_of_care"}, "text": "Spandeck duty analysis"}
    }
    verifier._authorities_indexes["sg_tort"] = {}

    report = await verifier.verify_model_answer(_answer(), corpus_pack="sg_tort")

    assert report.total_citations == 1
    assert report.verified == 1
    assert report.citation_accuracy == 1.0


@pytest.mark.asyncio
async def test_verify_model_answer_reports_unknown_and_topic_mismatch():
    verifier = CitationVerifier()
    verifier._corpus_indexes["sg_tort"] = {
        "wrong": {"topics": {"defamation"}, "text": "Publication and reputation"}
    }
    verifier._authorities_indexes["sg_tort"] = {}
    answer = _answer(
        citations=[
            CorpusRef(corpus_id="wrong"),
            CorpusRef(corpus_id="missing"),
        ]
    )

    report = await verifier.verify_model_answer(answer, corpus_pack="sg_tort")

    assert report.total_citations == 2
    assert report.verified == 0
    assert report.unknown_corpus_ids == ["missing"]
    assert report.topic_mismatch[0]["corpus_id"] == "wrong"


@pytest.mark.asyncio
async def test_verify_model_answer_accepts_authority_id_fallback():
    verifier = CitationVerifier()
    verifier._corpus_indexes["sg_tort"] = {}
    verifier._authorities_indexes["sg_tort"] = {
        "spandeck_2007": {"topics": {"duty_of_care"}, "citation": "Spandeck"}
    }
    answer = _answer(
        citations=[CorpusRef(corpus_id="not_in_corpus", authority_id="spandeck_2007")]
    )

    report = await verifier.verify_model_answer(answer, corpus_pack="sg_tort")

    assert report.verified == 1
    assert report.unknown_corpus_ids == []


def test_issue_to_topic_uses_domain_pack_aliases():
    assert _issue_to_topic("Whether there was a duty of care?") == "duty_of_care"


@pytest.mark.asyncio
async def test_generate_model_answer_attaches_citation_report(monkeypatch):
    service = HypotheticalService()
    service.llm_service = AsyncMock()
    service.llm_service.generate_structured = AsyncMock(return_value=_answer())
    validation = ValidationResult()
    monkeypatch.setattr(settings, "structured_generation_enabled", True)
    verifier_module = importlib.import_module(
        "src.services.verification.citation_verifier"
    )
    monkeypatch.setattr(
        verifier_module.citation_verifier,
        "verify_model_answer",
        AsyncMock(
            return_value=CitationReport(
                citation_accuracy=1.0,
                total_citations=1,
                verified=1,
            )
        ),
    )

    model_answer = await service._generate_model_answer(
        GenerationRequest(topics=["duty_of_care"]),
        "The rider hit a pedestrian.",
        validation,
        [
            cast(
                Any,
                SimpleNamespace(
                    id="c1",
                    text="A duty of care may arise under Spandeck.",
                    topics=["duty_of_care"],
                ),
            )
        ],
    )

    assert "Issue 1:" in model_answer
    assert validation.citation is not None
    assert validation.citation["verified"] == 1


@pytest.mark.asyncio
async def test_generate_model_answer_falls_back_to_text_without_citation(monkeypatch):
    service = HypotheticalService()
    service.llm_service = AsyncMock()
    service.llm_service.generate_structured = AsyncMock(
        side_effect=NotImplementedError("unsupported")
    )
    service.llm_service.generate = AsyncMock(
        return_value=SimpleNamespace(content="text answer")
    )
    validation = ValidationResult()
    monkeypatch.setattr(settings, "structured_generation_enabled", True)

    model_answer = await service._generate_model_answer(
        GenerationRequest(topics=["negligence"]),
        "The rider hit a pedestrian.",
        validation,
    )

    assert model_answer == "text answer"
    assert validation.citation is None
