"""Pydantic schemas for structured IRAC-typed generation.

These schemas are the contract between the LLM layer, the structured decoding
adapter (`structured.py`), the validation/verification stages (nli_verifier,
citation_verifier), the refine loop, and the eval harness.

They are pack-agnostic; jurisdiction/subject-specific vocab lives in the
corpus pack manifest and authorities index, not in the schema.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


class CorpusRef(BaseModel):
    """Reference to a corpus entry used to ground a claim or citation."""

    corpus_id: str = Field(description="Canonical corpus entry id, e.g. sg_tort_neg_001")
    authority_id: str | None = Field(
        default=None,
        description="Optional authorities.json id, e.g. spandeck_2007",
    )
    citation: str | None = Field(
        default=None,
        description="Full citation string, e.g. Spandeck Engineering v DSTA [2007] SGCA 37",
    )
    span: str | None = Field(
        default=None,
        description="Optional supporting span from the corpus text",
    )


class Party(BaseModel):
    """A named actor in the fact pattern."""

    name: str
    role: str = Field(description="claimant | defendant | third party | witness | context")
    description: str | None = None


class FactPattern(BaseModel):
    """The narrative fact pattern for the hypothetical."""

    setting: str = Field(description="Location, time, context (e.g., Marina Bay Sands, 2024)")
    narrative: str = Field(min_length=100, description="The fact pattern body")
    key_events: list[str] = Field(default_factory=list, description="Bulleted key events in order")


class Issue(BaseModel):
    """A legal issue raised by the fact pattern."""

    topic: str = Field(description="Canonical taxonomy topic key, e.g. duty_of_care")
    question: str = Field(description="The legal question the fact pattern raises")


class IRACStep(BaseModel):
    """A single IRAC (Issue-Rule-Application-Conclusion) reasoning step."""

    issue: str = Field(min_length=10, description="Statement of the legal issue")
    rule: str = Field(min_length=20, description="Applicable rule and its source")
    application: str = Field(
        min_length=40, description="Application of rule to the facts"
    )
    conclusion: str = Field(min_length=20, description="Reasoned conclusion")
    citations: list[CorpusRef] = Field(
        default_factory=list,
        description="Corpus references that support this step. Empty list allowed; refine loop will flag steps with zero citations.",
    )

    @field_validator("citations")
    @classmethod
    def _dedupe_citations(cls, v: list[CorpusRef]) -> list[CorpusRef]:
        seen: set[str] = set()
        deduped: list[CorpusRef] = []
        for ref in v:
            key = f"{ref.corpus_id}|{ref.authority_id or ''}"
            if key in seen:
                continue
            seen.add(key)
            deduped.append(ref)
        return deduped


class HypotheticalDraft(BaseModel):
    """Structured draft output of stage-1 generation.

    Downstream validators consume this shape directly, so the regex-based
    party/topic extraction in validation_service.py is only exercised as
    a fallback when a provider does not support structured decoding.
    """

    corpus_pack: str = Field(default="sg_tort")
    jurisdiction: str = Field(default="sg")
    subject: str = Field(default="tort")
    requested_topics: list[str] = Field(default_factory=list)
    facts: FactPattern
    parties: list[Party] = Field(default_factory=list)
    issues: list[Issue] = Field(default_factory=list)
    text: str = Field(
        description="Flat narrative rendering — kept for backward compatibility with the current API contract"
    )


class ModelAnswer(BaseModel):
    """Structured model-answer output of the staged IRAC chain."""

    corpus_pack: str = Field(default="sg_tort")
    steps: list[IRACStep] = Field(min_length=1)
    overall_conclusion: str = Field(min_length=20)


class Claim(BaseModel):
    """A discrete factual claim extracted from generated text for NLI check.

    Extracted by nli_verifier.py during faithfulness scoring.
    """

    text: str = Field(min_length=5)
    span_start: int | None = None
    span_end: int | None = None


class ClaimVerdict(BaseModel):
    """Per-claim NLI result against retrieved context."""

    claim: Claim
    verdict: str = Field(description="entailment | neutral | contradiction | unverifiable")
    confidence: float = Field(ge=0.0, le=1.0)
    supporting_corpus_id: str | None = None


class FaithfulnessReport(BaseModel):
    """Aggregate NLI faithfulness result for a generated draft."""

    faithfulness_score: float = Field(ge=0.0, le=1.0, description="Fraction of claims entailed")
    total_claims: int = Field(ge=0)
    entailed: int = Field(ge=0)
    contradicted: int = Field(ge=0)
    unverifiable: int = Field(ge=0)
    verdicts: list[ClaimVerdict] = Field(default_factory=list)


class CitationReport(BaseModel):
    """Aggregate citation-grounding result for a ModelAnswer."""

    citation_accuracy: float = Field(ge=0.0, le=1.0)
    total_citations: int = Field(ge=0)
    verified: int = Field(ge=0)
    unknown_corpus_ids: list[str] = Field(default_factory=list)
    topic_mismatch: list[dict[str, Any]] = Field(default_factory=list)


class RefineCritique(BaseModel):
    """Structured critique fed back to the LLM during self-refine."""

    iteration: int = Field(ge=0)
    missing_topics: list[str] = Field(default_factory=list)
    ml_gate: dict[str, Any] = Field(default_factory=dict)
    faithfulness: FaithfulnessReport | None = None
    citation: CitationReport | None = None
    rule_based: dict[str, Any] = Field(default_factory=dict)

    def is_blocking(self) -> bool:
        if self.missing_topics:
            return True
        if self.ml_gate and not self.ml_gate.get("passed", True):
            return True
        if self.faithfulness and self.faithfulness.faithfulness_score < 0.7:
            return True
        if self.citation and self.citation.citation_accuracy < 0.6:
            return True
        rb = self.rule_based or {}
        if isinstance(rb, dict) and rb.get("passed") is False:
            return True
        return False


__all__ = [
    "CorpusRef",
    "Party",
    "FactPattern",
    "Issue",
    "IRACStep",
    "HypotheticalDraft",
    "ModelAnswer",
    "Claim",
    "ClaimVerdict",
    "FaithfulnessReport",
    "CitationReport",
    "RefineCritique",
]
