"""Evaluator registry for SG-LegalBench datasets."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any, ClassVar

from .models import EvalCase, EvaluatorResult


@dataclass(frozen=True)
class EvaluatorContext:
    case: EvalCase
    output: str


class BaseEvaluator:
    name: ClassVar[str]

    async def evaluate(self, ctx: EvaluatorContext) -> EvaluatorResult:
        raise NotImplementedError

    def result(
        self,
        score: float,
        *,
        threshold: float = 1.0,
        details: dict[str, Any] | None = None,
    ) -> EvaluatorResult:
        bounded = max(0.0, min(1.0, score))
        return EvaluatorResult(
            name=self.name,
            score=bounded,
            passed=bounded >= threshold,
            details=details or {},
        )


def _list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _metadata_float(metadata: dict[str, Any], key: str, field: str) -> float | None:
    report = metadata.get(key)
    if report is None:
        return None
    try:
        return float(_field(report, field))
    except (TypeError, ValueError):
        return None


def _metadata_int(metadata: dict[str, Any], key: str, field: str) -> int | None:
    report = metadata.get(key)
    if report is None:
        return None
    try:
        return int(_field(report, field))
    except (TypeError, ValueError):
        return None


class ContainsExpected(BaseEvaluator):
    name = "contains"

    async def evaluate(self, ctx: EvaluatorContext) -> EvaluatorResult:
        terms = list(ctx.case.expected_output.get("contains", []))
        if not terms:
            return self.result(1.0, details={"matched": [], "missing": []})
        lowered = ctx.output.lower()
        matched = [term for term in terms if str(term).lower() in lowered]
        missing = [term for term in terms if term not in matched]
        return self.result(
            len(matched) / len(terms),
            details={"matched": matched, "missing": missing},
        )


class HasLegalCitation(BaseEvaluator):
    name = "has_citation"
    markers: ClassVar[tuple[str, ...]] = (
        "Act",
        "Section",
        "[",
        "]",
        "SGHC",
        "SGCA",
        "SLR",
        "Cap.",
        "s ",
        "s.",
    )

    async def evaluate(self, ctx: EvaluatorContext) -> EvaluatorResult:
        matched = [marker for marker in self.markers if marker in ctx.output]
        return self.result(1.0 if matched else 0.0, details={"matched": matched})


class MinLength(BaseEvaluator):
    name = "min_length"

    async def evaluate(self, ctx: EvaluatorContext) -> EvaluatorResult:
        min_chars = int(ctx.case.expected_output.get("min_length", 50))
        return self.result(
            1.0 if len(ctx.output) >= min_chars else 0.0,
            details={"min_chars": min_chars, "actual_chars": len(ctx.output)},
        )


class IsString(BaseEvaluator):
    name = "is_string"

    async def evaluate(self, ctx: EvaluatorContext) -> EvaluatorResult:
        return self.result(1.0 if isinstance(ctx.output, str) else 0.0)


class HasSgCitation(BaseEvaluator):
    name = "has_sg_citation"
    citation_re: ClassVar[re.Pattern[str]] = re.compile(
        r"\[(?:19|20)\d{2}\]\s+(?:SGCA|SGHC|SGCA\(I\)|SGHC\(I\)|SGHCR|SGDC|SGMC|SGFC|SICC)\s+\d+"
        r"|\[(?:19|20)\d{2}\]\s+\d+\s+SLR(?:\(R\))?\s+\d+"
    )

    async def evaluate(self, ctx: EvaluatorContext) -> EvaluatorResult:
        matches = self.citation_re.findall(ctx.output)
        return self.result(1.0 if matches else 0.0, details={"matches": matches})


class CitesSgStatute(BaseEvaluator):
    name = "cites_sg_statute"
    known_acts: ClassVar[tuple[str, ...]] = (
        "Civil Law Act",
        "Contributory Negligence and Personal Injuries Act",
        "Defamation Act",
        "Evidence Act",
        "Limitation Act",
        "Penal Code",
        "Protection from Harassment Act",
        "Road Traffic Act",
        "State Courts Act",
        "Supreme Court of Judicature Act",
        "Unfair Contract Terms Act",
        "Work Injury Compensation Act",
        "Workplace Safety and Health Act",
    )
    section_re: ClassVar[re.Pattern[str]] = re.compile(
        r"\b(?:s|section)\.?\s*\d+[A-Z]?(?:\(\d+[A-Z]?\))*\b",
        re.IGNORECASE,
    )

    async def evaluate(self, ctx: EvaluatorContext) -> EvaluatorResult:
        required = list(ctx.case.expected_output.get("statutes", []))
        act_terms = required or list(self.known_acts)
        matched = [act for act in act_terms if act.lower() in ctx.output.lower()]
        has_section = bool(self.section_re.search(ctx.output))
        if required:
            score = (len(matched) / len(required) + float(has_section)) / 2
        else:
            score = 1.0 if matched and has_section else 0.0
        return self.result(
            score,
            details={"matched": matched, "has_section": has_section},
        )


class UsesSalStyle(BaseEvaluator):
    name = "uses_sal_style"
    bad_re: ClassVar[re.Pattern[str]] = re.compile(
        r"\bvs\.?\b|\bversus\b|\bSection\s+\d+",
        re.IGNORECASE,
    )
    good_re: ClassVar[re.Pattern[str]] = re.compile(
        r"\b[A-Z][A-Za-z&.' -]+ v [A-Z][A-Za-z&.' -]+\b"
        r"|\[(?:19|20)\d{2}\]\s+(?:SG|SLR)"
        r"|\bs\.?\s*\d+",
        re.IGNORECASE,
    )

    async def evaluate(self, ctx: EvaluatorContext) -> EvaluatorResult:
        bad = self.bad_re.findall(ctx.output)
        good = self.good_re.findall(ctx.output)
        if bad:
            score = 0.0
        elif good:
            score = 1.0
        else:
            score = 0.5
        return self.result(score, details={"bad": bad, "good": good})


class TortElementCoverage(BaseEvaluator):
    name = "tort_element_coverage"

    async def evaluate(self, ctx: EvaluatorContext) -> EvaluatorResult:
        elements = ctx.case.expected_output.get(
            "tort_elements", ["duty", "breach", "causation", "damage"]
        )
        lowered = ctx.output.lower()
        matched = []
        for element in elements:
            term = str(element).lower()
            if term == "damage":
                found = "damage" in lowered or "damages" in lowered
            else:
                found = term in lowered
            if found:
                matched.append(element)
        return self.result(
            len(matched) / len(elements) if elements else 1.0,
            details={"matched": matched, "required": elements},
        )


class RetrievalRecallAtK(BaseEvaluator):
    name = "retrieval_recall_at_k"

    async def evaluate(self, ctx: EvaluatorContext) -> EvaluatorResult:
        gold = {
            str(item)
            for item in _list(ctx.case.expected_output.get("relevant_corpus_ids"))
        }
        retrieved = [
            str(item) for item in _list(ctx.case.metadata.get("retrieved_ids"))
        ]
        k = int(ctx.case.expected_output.get("recall_k", 5))
        if not gold:
            return self.result(1.0, details={"reason": "no_gold"})
        top_k = retrieved[:k]
        hit = len(gold & set(top_k))
        return self.result(
            hit / len(gold),
            details={
                "k": k,
                "hit": hit,
                "gold_size": len(gold),
                "retrieved_top_k": top_k,
            },
        )


class RetrievalMRR(BaseEvaluator):
    name = "retrieval_mrr"

    async def evaluate(self, ctx: EvaluatorContext) -> EvaluatorResult:
        gold = {
            str(item)
            for item in _list(ctx.case.expected_output.get("relevant_corpus_ids"))
        }
        retrieved = [
            str(item) for item in _list(ctx.case.metadata.get("retrieved_ids"))
        ]
        if not gold:
            return self.result(1.0, details={"reason": "no_gold"})
        rank = next(
            (
                index
                for index, corpus_id in enumerate(retrieved, start=1)
                if corpus_id in gold
            ),
            None,
        )
        score = 1.0 / rank if rank else 0.0
        return self.result(score, details={"rank": rank, "gold_size": len(gold)})


class RetrievalNDCG(BaseEvaluator):
    name = "retrieval_ndcg"

    async def evaluate(self, ctx: EvaluatorContext) -> EvaluatorResult:
        gold = {
            str(item)
            for item in _list(ctx.case.expected_output.get("relevant_corpus_ids"))
        }
        retrieved = [
            str(item) for item in _list(ctx.case.metadata.get("retrieved_ids"))
        ]
        k = int(ctx.case.expected_output.get("recall_k", 5))
        if not gold:
            return self.result(1.0, details={"reason": "no_gold"})
        relevance = [1.0 if corpus_id in gold else 0.0 for corpus_id in retrieved[:k]]
        dcg = sum(rel / math.log2(index + 2) for index, rel in enumerate(relevance))
        ideal_count = min(k, len(gold))
        idcg = sum(1.0 / math.log2(index + 2) for index in range(ideal_count))
        score = dcg / idcg if idcg else 0.0
        return self.result(
            score,
            details={"k": k, "dcg": dcg, "idcg": idcg, "relevance": relevance},
        )


class RAGASFaithfulness(BaseEvaluator):
    name = "ragas_faithfulness"

    async def evaluate(self, ctx: EvaluatorContext) -> EvaluatorResult:
        score = _metadata_float(
            ctx.case.metadata, "faithfulness_report", "faithfulness_score"
        )
        if score is None:
            return self.result(0.0, threshold=0.7, details={"reason": "missing_report"})
        return self.result(score, threshold=0.7)


class CitationAccuracy(BaseEvaluator):
    name = "citation_accuracy"

    async def evaluate(self, ctx: EvaluatorContext) -> EvaluatorResult:
        score = _metadata_float(
            ctx.case.metadata, "citation_report", "citation_accuracy"
        )
        if score is None:
            return self.result(0.0, threshold=0.6, details={"reason": "missing_report"})
        return self.result(score, threshold=0.6)


class HallucinationProfile(BaseEvaluator):
    name = "hallucination_profile"

    async def evaluate(self, ctx: EvaluatorContext) -> EvaluatorResult:
        total = _metadata_int(ctx.case.metadata, "faithfulness_report", "total_claims")
        unverifiable = _metadata_int(
            ctx.case.metadata, "faithfulness_report", "unverifiable"
        )
        if total is None or unverifiable is None:
            return self.result(0.0, threshold=0.7, details={"reason": "missing_report"})
        if total <= 0:
            return self.result(1.0, threshold=0.7, details={"reason": "no_claims"})
        fraction = unverifiable / total
        return self.result(
            1.0 - fraction,
            threshold=0.7,
            details={
                "total_claims": total,
                "unverifiable": unverifiable,
                "unverifiable_fraction": fraction,
            },
        )


class IRACCompleteness(BaseEvaluator):
    name = "irac_completeness"

    async def evaluate(self, ctx: EvaluatorContext) -> EvaluatorResult:
        answer = ctx.case.metadata.get("model_answer") or {}
        steps = _list(_field(answer, "steps", []))
        if not steps:
            return self.result(0.0, threshold=0.8, details={"reason": "no_steps"})
        complete = 0
        for step in steps:
            has_text = all(
                bool(str(_field(step, field, "")).strip())
                for field in ("issue", "rule", "application", "conclusion")
            )
            has_citation = bool(_list(_field(step, "citations", [])))
            if has_text and has_citation:
                complete += 1
        score = complete / len(steps)
        return self.result(
            score,
            threshold=0.8,
            details={"complete_steps": complete, "total_steps": len(steps)},
        )


EVALUATORS: dict[str, BaseEvaluator] = {
    "contains": ContainsExpected(),
    "has_citation": HasLegalCitation(),
    "min_length": MinLength(),
    "is_string": IsString(),
    "has_sg_citation": HasSgCitation(),
    "cites_sg_statute": CitesSgStatute(),
    "uses_sal_style": UsesSalStyle(),
    "tort_element_coverage": TortElementCoverage(),
    "retrieval_recall_at_k": RetrievalRecallAtK(),
    "retrieval_mrr": RetrievalMRR(),
    "retrieval_ndcg": RetrievalNDCG(),
    "ragas_faithfulness": RAGASFaithfulness(),
    "citation_accuracy": CitationAccuracy(),
    "hallucination_profile": HallucinationProfile(),
    "irac_completeness": IRACCompleteness(),
}

__all__ = [
    "EVALUATORS",
    "BaseEvaluator",
    "EvaluatorContext",
    "ContainsExpected",
    "HasLegalCitation",
    "MinLength",
    "IsString",
    "HasSgCitation",
    "CitesSgStatute",
    "UsesSalStyle",
    "TortElementCoverage",
    "RetrievalRecallAtK",
    "RetrievalMRR",
    "RetrievalNDCG",
    "RAGASFaithfulness",
    "CitationAccuracy",
    "HallucinationProfile",
    "IRACCompleteness",
]
