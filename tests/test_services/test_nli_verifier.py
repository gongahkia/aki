"""Tests for NLI faithfulness verification."""

import importlib
import os
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.config import settings
from src.services.hypothetical_service import (
    GenerationRequest,
    HypotheticalService,
    ValidationResult,
)
from src.services.prompt_engineering.schemas import Claim, FaithfulnessReport
from src.services.verification import NLIFaithfulnessVerifier


class FakeCrossEncoder:
    def predict(self, pairs: list[tuple[str, str]]) -> list[list[float]]:
        premise, hypothesis = pairs[0]
        if "collided with a pedestrian" in premise and "hit a pedestrian" in hypothesis:
            return [[0.1, 4.0, 0.2]]
        if "never entered Marina Bay" in premise and "Marina Bay" in hypothesis:
            return [[4.0, 0.1, 0.2]]
        return [[0.1, 0.2, 4.0]]


@pytest.mark.asyncio
async def test_extract_claims_uses_llm_json():
    verifier = NLIFaithfulnessVerifier()
    llm = AsyncMock()
    llm.generate = AsyncMock(
        return_value=SimpleNamespace(content='[{"text":"The rider hit a pedestrian."}]')
    )

    claims = await verifier.extract_claims("body", llm)

    assert claims == [Claim(text="The rider hit a pedestrian.")]


@pytest.mark.asyncio
async def test_extract_claims_falls_back_to_sentence_split():
    verifier = NLIFaithfulnessVerifier()
    llm = AsyncMock()
    llm.generate = AsyncMock(side_effect=RuntimeError("no json mode"))

    claims = await verifier.extract_claims(
        "The rider hit a pedestrian. The barrier was broken.", llm
    )

    assert [claim.text for claim in claims] == [
        "The rider hit a pedestrian.",
        "The barrier was broken.",
    ]


def test_verify_scores_claims_against_contexts_with_softmax_confidence():
    verifier = NLIFaithfulnessVerifier()
    verifier._model = FakeCrossEncoder()

    report = verifier.verify(
        [Claim(text="The rider hit a pedestrian at Marina Bay.")],
        [
            {
                "corpus_id": "c1",
                "text": "The rider collided with a pedestrian at Marina Bay.",
            }
        ],
    )

    assert report.entailed == 1
    assert report.faithfulness_score == 1.0
    assert 0.0 <= report.verdicts[0].confidence <= 1.0
    assert report.verdicts[0].supporting_corpus_id == "c1"


def test_verify_degrades_to_unverifiable_without_model():
    verifier = NLIFaithfulnessVerifier()
    verifier._model = False

    report = verifier.verify([Claim(text="The rider hit a pedestrian.")], [])

    assert report.faithfulness_score == 0.0
    assert report.unverifiable == 1
    assert report.verdicts[0].verdict == "unverifiable"


@pytest.mark.asyncio
async def test_validate_hypothetical_attaches_faithfulness(monkeypatch):
    service = HypotheticalService()
    service_any = cast(Any, service)
    service.validation_service = MagicMock()
    service.validation_service.validate_hypothetical.return_value = {
        "overall_score": 8.0,
        "passed": True,
        "checks": {
            "legal_realism": {"realism_score": 1.0},
            "exam_likeness": {"exam_likeness_score": 1.0},
        },
        "quality_gate": {},
    }
    service.validation_service.validate_with_llm = AsyncMock(return_value={})
    service_any._check_text_similarity = AsyncMock(
        return_value={"passed": True, "max_similarity": 0.1}
    )
    monkeypatch.setattr(settings, "nli_verifier_enabled", True)

    verifier_module = importlib.import_module("src.services.verification.nli_verifier")

    monkeypatch.setattr(
        verifier_module.nli_verifier,
        "extract_claims",
        AsyncMock(return_value=[Claim(text="The rider hit a pedestrian.")]),
    )
    monkeypatch.setattr(
        verifier_module.nli_verifier,
        "verify",
        lambda claims, contexts: FaithfulnessReport(
            faithfulness_score=1.0,
            total_claims=1,
            entailed=1,
            contradicted=0,
            unverifiable=0,
        ),
    )

    result = await service._validate_hypothetical(
        GenerationRequest(topics=["negligence"]),
        "The rider hit a pedestrian.",
        cast(
            Any,
            [SimpleNamespace(id="c1", text="A rider hit a pedestrian.", topics=[])],
        ),
    )

    assert isinstance(result, ValidationResult)
    assert result.faithfulness is not None
    assert result.faithfulness["entailed"] == 1


@pytest.mark.integration
def test_real_cross_encoder_toy_inputs_when_enabled():
    if os.getenv("JIKAI_RUN_REAL_NLI") != "1":
        pytest.skip("set JIKAI_RUN_REAL_NLI=1 to run real CrossEncoder smoke")
    verifier = NLIFaithfulnessVerifier()
    report = verifier.verify(
        [Claim(text="The delivery rider hit a pedestrian at Marina Bay.")],
        [
            {
                "corpus_id": "t1",
                "text": "A rider collided with a pedestrian in Marina Bay.",
            }
        ],
    )
    assert report.entailed >= 1
