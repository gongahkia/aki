"""NLI-based faithfulness verifier for generated hypotheticals."""

from __future__ import annotations

import json
import math
import re
from typing import Any

import structlog
from pydantic import ValidationError

from ...config import settings
from ..prompt_engineering.schemas import Claim, ClaimVerdict, FaithfulnessReport

logger = structlog.get_logger(__name__)

_NLI_LABELS = ["contradiction", "entailment", "neutral"]


class NLIFaithfulnessVerifier:
    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or settings.nli_verifier_model
        self._model: Any = None

    def _load(self) -> Any:
        if self._model is None:
            try:
                from sentence_transformers import CrossEncoder

                self._model = CrossEncoder(self.model_name)
            except Exception as exc:
                logger.warning(
                    "NLI model unavailable; verifier will noop", error=str(exc)
                )
                self._model = False
        return self._model

    async def extract_claims(self, text: str, llm_service_ref: Any) -> list[Claim]:
        try:
            from ..llm_service import LLMRequest

            resp = await llm_service_ref.generate(
                LLMRequest(
                    prompt=self._extraction_prompt(text),
                    temperature=0.0,
                    max_tokens=1024,
                )
            )
            raw = json.loads(_strip_code_fence(str(resp.content)))
            items = _claim_items(raw)
            claims = [_claim_from_item(item) for item in items]
            return [claim for claim in claims if claim is not None]
        except Exception as exc:
            logger.info(
                "Falling back to sentence-splitting for claim extraction",
                error=str(exc),
            )
            return [
                Claim(text=sentence.strip())
                for sentence in re.split(r"(?<=[.!?])\s+", text)
                if len(sentence.strip()) >= 5
            ]

    def _extraction_prompt(self, text: str) -> str:
        return (
            "Extract discrete factual claims from the following legal hypothetical. "
            'Return ONLY a JSON list of {"text": str} objects. Only assertions '
            "about the world (parties, actions, causation, timing, location) are "
            "claims. No questions, headings, or restatements.\n\nText:\n" + text
        )

    def verify(
        self, claims: list[Claim], contexts: list[dict[str, str]]
    ) -> FaithfulnessReport:
        model = self._load()
        if not claims:
            return FaithfulnessReport(
                faithfulness_score=1.0,
                total_claims=0,
                entailed=0,
                contradicted=0,
                unverifiable=0,
            )
        if not model or not contexts:
            return _unverifiable_report(claims)

        verdicts: list[ClaimVerdict] = []
        entailed = contradicted = unverifiable = 0
        for claim in claims:
            verdict, confidence, source = self._best_verdict(model, claim, contexts)
            if verdict == "entailment":
                entailed += 1
            elif verdict == "contradiction":
                contradicted += 1
            else:
                unverifiable += 1
            verdicts.append(
                ClaimVerdict(
                    claim=claim,
                    verdict=verdict,
                    confidence=confidence,
                    supporting_corpus_id=source,
                )
            )

        total = len(claims)
        return FaithfulnessReport(
            faithfulness_score=entailed / total if total else 1.0,
            total_claims=total,
            entailed=entailed,
            contradicted=contradicted,
            unverifiable=unverifiable,
            verdicts=verdicts,
        )

    def _best_verdict(
        self,
        model: Any,
        claim: Claim,
        contexts: list[dict[str, str]],
    ) -> tuple[str, float, str | None]:
        best_verdict = "unverifiable"
        best_conf = 0.0
        best_source: str | None = None
        for ctx in contexts:
            text = str(ctx.get("text", "")).strip()
            if not text:
                continue
            scores = model.predict([(text, claim.text)])[0]
            probs = _softmax(_as_float_list(scores))
            if not probs:
                continue
            idx = max(range(len(probs)), key=lambda i: probs[i])
            label = _NLI_LABELS[idx] if idx < len(_NLI_LABELS) else "neutral"
            conf = float(probs[idx])
            corpus_id = str(ctx.get("corpus_id", "")).strip() or None
            if label == "entailment" and conf > best_conf:
                best_verdict, best_conf, best_source = "entailment", conf, corpus_id
            elif (
                label == "contradiction"
                and best_verdict != "entailment"
                and conf > best_conf
            ):
                best_verdict, best_conf, best_source = (
                    "contradiction",
                    conf,
                    corpus_id,
                )
        return best_verdict, best_conf, best_source


def _unverifiable_report(claims: list[Claim]) -> FaithfulnessReport:
    return FaithfulnessReport(
        faithfulness_score=0.0,
        total_claims=len(claims),
        entailed=0,
        contradicted=0,
        unverifiable=len(claims),
        verdicts=[
            ClaimVerdict(claim=claim, verdict="unverifiable", confidence=0.0)
            for claim in claims
        ],
    )


def _claim_items(raw: Any) -> list[Any]:
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        for key in ("claims", "items", "data"):
            value = raw.get(key)
            if isinstance(value, list):
                return value
    return []


def _claim_from_item(item: Any) -> Claim | None:
    try:
        if isinstance(item, dict):
            text = str(item.get("text", "")).strip()
            if text:
                return Claim(text=text)
        elif isinstance(item, str) and item.strip():
            return Claim(text=item.strip())
    except ValidationError:
        return None
    return None


def _as_float_list(scores: Any) -> list[float]:
    if hasattr(scores, "tolist"):
        scores = scores.tolist()
    if isinstance(scores, (int, float)):
        return [float(scores)]
    try:
        return [float(score) for score in scores]
    except TypeError:
        return []


def _softmax(scores: list[float]) -> list[float]:
    if not scores:
        return []
    max_score = max(scores)
    exps = [math.exp(score - max_score) for score in scores]
    denom = sum(exps)
    if denom <= 0:
        return []
    return [value / denom for value in exps]


def _strip_code_fence(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s)
        s = re.sub(r"\s*```$", "", s)
    return s


nli_verifier = NLIFaithfulnessVerifier()

__all__ = ["NLIFaithfulnessVerifier", "nli_verifier"]
