"""Structured entity extraction and soft consistency checks for SG hypotheticals."""

from __future__ import annotations

import re
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

KNOWN_SG_COURTS = {
    "SGCA",
    "SGHC",
    "SGHC(I)",
    "SGHCR",
    "SGDC",
    "SGMC",
    "SGFC",
    "SICC",
}

KNOWN_SG_ACTS = {
    "civil law act",
    "contributory negligence and personal injuries act",
    "defamation act",
    "evidence act",
    "limitation act",
    "penal code",
    "protection from harassment act",
    "road traffic act",
    "state courts act",
    "supreme court of judicature act",
    "unfair contract terms act",
    "work injury compensation act",
    "workplace safety and health act",
}

CASE_CITATION_RE = re.compile(
    r"\[(?P<year>\d{4})\]\s+(?P<court>[A-Z][A-Z0-9()]{1,12})\s+(?P<number>\d+)"
)
CASE_CITATION_LIKE_RE = re.compile(
    r"\[(?P<year>\d{4})\]\s+(?P<court>[A-Z][A-Z0-9()]{1,12})\s+(?P<number>[A-Za-z0-9]+)"
)
CASE_NAME_RE = re.compile(
    r"([A-Z][A-Za-z0-9&'()., -]{1,80}\s+v\.?\s+[A-Z][A-Za-z0-9&'()., -]{1,80})\s*$"
)
STATUTE_RE = re.compile(
    r"(?:(?P<provision>(?:s|section)\.?\s*\d+[A-Za-z]?(?:\(\d+[A-Za-z]?\))*)\s+(?:of\s+the\s+)?)?"
    r"(?P<title>[A-Z][A-Za-z&'() -]+ Act(?:\s+\d{4})?)"
)
MONEY_RE = re.compile(r"\b(?:S\$|SGD\s*|\$)\s?\d{1,3}(?:,\d{3})*(?:\.\d+)?\b")
DATE_RE = re.compile(
    r"\b(?:\d{4}-\d{2}-\d{2}|\d{1,2}\s+"
    r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+\d{4})\b"
)
COMPANY_RE = re.compile(
    r"\b[A-Z][A-Za-z&]*(?:\s+[A-Z][A-Za-z&]*){0,3}\s+"
    r"(?:Pte Ltd|Ltd|LLP|LLC|Holdings|Services|Enterprises|Solutions)\b"
)
TITLED_PERSON_RE = re.compile(
    r"\b(?:Mr|Mrs|Ms|Dr|Prof)\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\b"
)
FULL_NAME_RE = re.compile(r"\b[A-Z][a-z]+(?:\s+(?:bin|binti))?\s+[A-Z][a-z]+\b")
JUDGE_RE = re.compile(
    r"\b(?:(?:Chief\s+Justice|Justice|Judge)\s+"
    r"(?P<prefix>[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})|"
    r"(?P<suffix>[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\s+CJ)\b"
)

ENTITY_EXCLUSIONS = {
    "Court",
    "High Court",
    "Court Appeal",
    "Singapore",
    "Civil Law",
    "Penal Code",
    "Road Traffic",
    "State Courts",
    "Supreme Court",
    "Work Injury",
    "Workplace Safety",
}

SG_LOCATION_CUES = [
    "Ang Mo Kio",
    "Bedok",
    "Bukit Timah",
    "Changi",
    "Chinatown",
    "Clementi",
    "High Court",
    "HDB",
    "Jurong",
    "Little India",
    "Marina Bay",
    "MRT",
    "Orchard Road",
    "Raffles",
    "Sentosa",
    "Singapore",
    "State Courts",
    "Tampines",
    "Toa Payoh",
    "Woodlands",
]


class ExtractedParty(BaseModel):
    name: str
    kind: Literal["person", "organisation"] = "person"


class ExtractedJudge(BaseModel):
    name: str


class ExtractedCaseCitation(BaseModel):
    citation: str
    year: int
    court: str
    number: str
    case_name: str | None = None
    valid_format: bool = True


class ExtractedStatuteReference(BaseModel):
    raw: str
    title: str
    normalized_title: str
    provision: str | None = None
    known: bool


class ExtractedMonetaryAmount(BaseModel):
    raw: str


class ExtractedDateReference(BaseModel):
    raw: str


class ExtractedLocation(BaseModel):
    name: str


class ExtractedEntities(BaseModel):
    parties: list[ExtractedParty] = Field(default_factory=list)
    judges: list[ExtractedJudge] = Field(default_factory=list)
    citations: list[ExtractedCaseCitation] = Field(default_factory=list)
    statutes: list[ExtractedStatuteReference] = Field(default_factory=list)
    monetary_amounts: list[ExtractedMonetaryAmount] = Field(default_factory=list)
    dates: list[ExtractedDateReference] = Field(default_factory=list)
    locations: list[ExtractedLocation] = Field(default_factory=list)


class EntityValidationIssue(BaseModel):
    code: str
    severity: Literal["warning", "error"]
    message: str
    evidence: str


class EntityConsistencyResult(BaseModel):
    passed: bool
    soft_failures: bool
    issue_count: int
    issues: list[EntityValidationIssue] = Field(default_factory=list)
    entities: ExtractedEntities
    skipped_checks: list[str] = Field(default_factory=list)


def _normalize_statute_title(title: str) -> str:
    normalized = title.replace("’", "'").strip().lower()
    normalized = re.sub(r"^the\s+", "", normalized)
    normalized = re.sub(r"\s+\d{4}$", "", normalized)
    normalized = re.sub(r"[^a-z0-9&'() -]+", "", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _dedupe_models(items: list[BaseModel], key: str) -> list[BaseModel]:
    seen: set[str] = set()
    deduped: list[BaseModel] = []
    for item in items:
        value = str(getattr(item, key)).lower()
        if value in seen:
            continue
        seen.add(value)
        deduped.append(item)
    return deduped


class EntityConsistencyValidator:
    """Deterministic extractor and soft validator for generated hypotheticals."""

    def __init__(self, *, current_year: int | None = None):
        self.current_year = current_year or date.today().year

    def extract(self, text: str, *, jurisdiction: str = "sg") -> ExtractedEntities:
        parties: list[ExtractedParty] = []
        for match in COMPANY_RE.finditer(text):
            parties.append(ExtractedParty(name=match.group(0), kind="organisation"))
        for pattern in (TITLED_PERSON_RE, FULL_NAME_RE):
            for match in pattern.finditer(text):
                name = match.group(0).strip()
                if name in ENTITY_EXCLUSIONS:
                    continue
                parties.append(ExtractedParty(name=name, kind="person"))

        judges = []
        for match in JUDGE_RE.finditer(text):
            name = match.group("prefix") or match.group("suffix")
            if name:
                judges.append(ExtractedJudge(name=name))

        citations = self._extract_citations(text)
        statutes = self._extract_statutes(text, jurisdiction=jurisdiction)
        monetary = [
            ExtractedMonetaryAmount(raw=m.group(0)) for m in MONEY_RE.finditer(text)
        ]
        dates = [ExtractedDateReference(raw=m.group(0)) for m in DATE_RE.finditer(text)]
        locations = [
            ExtractedLocation(name=cue)
            for cue in SG_LOCATION_CUES
            if re.search(rf"\b{re.escape(cue)}\b", text, re.IGNORECASE)
        ]

        return ExtractedEntities(
            parties=_dedupe_models(parties, "name"),
            judges=_dedupe_models(judges, "name"),
            citations=_dedupe_models(citations, "citation"),
            statutes=_dedupe_models(statutes, "raw"),
            monetary_amounts=_dedupe_models(monetary, "raw"),
            dates=_dedupe_models(dates, "raw"),
            locations=_dedupe_models(locations, "name"),
        )

    def validate(
        self,
        text: str,
        *,
        corpus_pack: str = "sg_tort",
        jurisdiction: str = "sg",
        subject: str = "tort",
    ) -> EntityConsistencyResult:
        entities = self.extract(text, jurisdiction=jurisdiction)
        issues: list[EntityValidationIssue] = []
        skipped_checks: list[str] = []

        if jurisdiction != "sg":
            skipped_checks.append("known_sg_statute_check")
            skipped_checks.append("known_sg_court_check")

        for citation in entities.citations:
            if not citation.valid_format:
                issues.append(
                    EntityValidationIssue(
                        code="invalid_case_citation_format",
                        severity="error",
                        message="Case citation does not parse as [year] COURT number.",
                        evidence=citation.citation,
                    )
                )
            if citation.year > self.current_year:
                issues.append(
                    EntityValidationIssue(
                        code="future_case_citation",
                        severity="error",
                        message="Case citation year is in the future.",
                        evidence=citation.citation,
                    )
                )
            if citation.number.isdigit() and int(citation.number) > 1000:
                issues.append(
                    EntityValidationIssue(
                        code="implausible_case_number",
                        severity="warning",
                        message="Case citation number is implausibly high for SG reports.",
                        evidence=citation.citation,
                    )
                )
            if jurisdiction == "sg" and citation.court not in KNOWN_SG_COURTS:
                issues.append(
                    EntityValidationIssue(
                        code="unknown_sg_court",
                        severity="warning",
                        message="Citation court code is not in the known SG court list.",
                        evidence=citation.citation,
                    )
                )

        if jurisdiction == "sg":
            for statute in entities.statutes:
                if not statute.known:
                    issues.append(
                        EntityValidationIssue(
                            code="unknown_sg_statute",
                            severity="warning",
                            message="Statute title is not in the known SG Act list.",
                            evidence=statute.raw,
                        )
                    )

        return EntityConsistencyResult(
            passed=not issues,
            soft_failures=bool(issues),
            issue_count=len(issues),
            issues=issues,
            entities=entities,
            skipped_checks=skipped_checks,
        )

    def _extract_citations(self, text: str) -> list[ExtractedCaseCitation]:
        citations: list[ExtractedCaseCitation] = []
        for match in CASE_CITATION_LIKE_RE.finditer(text):
            raw = match.group(0)
            year = int(match.group("year"))
            court = match.group("court")
            number = match.group("number")
            valid_format = bool(CASE_CITATION_RE.fullmatch(raw))
            prefix = text[max(0, match.start() - 120) : match.start()].strip()
            case_name_match = CASE_NAME_RE.search(prefix)
            citations.append(
                ExtractedCaseCitation(
                    citation=raw,
                    year=year,
                    court=court,
                    number=number,
                    case_name=case_name_match.group(1) if case_name_match else None,
                    valid_format=valid_format,
                )
            )
        return citations

    def _extract_statutes(
        self, text: str, *, jurisdiction: str
    ) -> list[ExtractedStatuteReference]:
        statutes: list[ExtractedStatuteReference] = []
        for match in STATUTE_RE.finditer(text):
            raw = match.group(0).strip()
            title = match.group("title").strip()
            normalized = _normalize_statute_title(title)
            statutes.append(
                ExtractedStatuteReference(
                    raw=raw,
                    title=title,
                    normalized_title=normalized,
                    provision=match.group("provision"),
                    known=jurisdiction != "sg" or normalized in KNOWN_SG_ACTS,
                )
            )
        return statutes


entity_consistency_validator = EntityConsistencyValidator()
