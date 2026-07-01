"""Evaluator registry for SG-LegalBench datasets."""

from __future__ import annotations

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
        self, score: float, *, details: dict[str, Any] | None = None
    ) -> EvaluatorResult:
        bounded = max(0.0, min(1.0, score))
        return EvaluatorResult(
            name=self.name,
            score=bounded,
            passed=bounded >= 1.0,
            details=details or {},
        )


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


EVALUATORS: dict[str, BaseEvaluator] = {
    "contains": ContainsExpected(),
    "has_citation": HasLegalCitation(),
    "min_length": MinLength(),
    "is_string": IsString(),
    "has_sg_citation": HasSgCitation(),
    "cites_sg_statute": CitesSgStatute(),
    "uses_sal_style": UsesSalStyle(),
    "tort_element_coverage": TortElementCoverage(),
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
]
