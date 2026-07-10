"""Build and validate metadata-only bar exam link records."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable
from urllib import error, parse, request

from src.corpus_source_registry import (
    SourceRegistryError,
    assert_derived_metadata_allowed,
    assert_text_commit_allowed,
)

DEFAULT_OUTPUT = Path("corpus/metadata/bar_exam_link_index/metadata.json")


@dataclass(frozen=True)
class SourceConfig:
    source_id: str
    name: str
    jurisdiction: str
    index_url: str


SOURCE_CONFIGS: dict[str, SourceConfig] = {
    "california_bar_past_exams": SourceConfig(
        source_id="california_bar_past_exams",
        name="California past exams",
        jurisdiction="us-ca",
        index_url="https://www.calbar.ca.gov/admissions/applicant-resources/past-exams",
    ),
    "ny_bole_exam_questions": SourceConfig(
        source_id="ny_bole_exam_questions",
        name="New York BOLE past questions/sample answers",
        jurisdiction="us-ny",
        index_url="https://www.nybarexam.org/ExamQuestions/ExamQuestions.htm",
    ),
    "texas_ble_selected_answers": SourceConfig(
        source_id="texas_ble_selected_answers",
        name="Texas BLE questions/selected answers",
        jurisdiction="us-tx",
        index_url="https://ble.texas.gov/selected-answers",
    ),
    "ncbe_study_aids": SourceConfig(
        source_id="ncbe_study_aids",
        name="NCBE official study aids",
        jurisdiction="us",
        index_url="https://www.ncbex.org/study-aids",
    ),
}

FORBIDDEN_TEXT_FIELDS = {
    "text",
    "content",
    "prompt",
    "question",
    "question_prompt",
    "answer",
    "sample_answer",
    "selected_answer",
    "model_answer",
    "rubric",
}

Fetch = Callable[[str], bytes]


@dataclass(frozen=True)
class Link:
    url: str
    text: str


class _LinkParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.links: list[Link] = []
        self._href: str | None = None
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        attrs_dict = {key.lower(): value for key, value in attrs}
        href = attrs_dict.get("href")
        if href:
            self._href = parse.urljoin(self.base_url, href)
            self._parts = []

    def handle_data(self, data: str) -> None:
        if self._href:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or not self._href:
            return
        text = _clean_text(" ".join(self._parts))
        self.links.append(Link(url=self._href, text=text))
        self._href = None
        self._parts = []


def _default_fetch(url: str) -> bytes:
    req = request.Request(url, headers={"user-agent": "jikai-metadata-crawler/1.0"})
    try:
        with request.urlopen(req, timeout=30) as resp:
            return resp.read()
    except error.URLError as exc:
        raise RuntimeError(f"failed to fetch {url}: {exc}") from exc


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _parse_links(html: bytes, base_url: str) -> list[Link]:
    parser = _LinkParser(base_url)
    parser.feed(html.decode("utf-8", errors="replace"))
    return parser.links


def _looks_like_pdf(url: str) -> bool:
    path = parse.urlparse(url).path.lower()
    return path.endswith(".pdf")


def _label(link: Link) -> str:
    fallback = Path(parse.urlparse(link.url).path).name.replace("-", " ")
    return _clean_text(f"{link.text} {fallback}")


def infer_subject(label: str) -> str:
    return "tort" if re.search(r"\btorts?\b", label, re.IGNORECASE) else "unknown"


def infer_component(label: str) -> str:
    lowered = label.lower()
    if "selected answer" in lowered or "sample answer" in lowered:
        return "sample_answer"
    if "performance test" in lowered or re.search(r"\bmpt\b", lowered):
        return "performance_test"
    if "essay" in lowered or re.search(r"\bmee\b", lowered):
        return "essay"
    if re.search(r"\bmbe\b", lowered) or "multiple choice" in lowered:
        return "multiple_choice"
    if "question" in lowered:
        return "question"
    return "unknown"


def infer_exam_date(label: str) -> str:
    months = {
        "jan": "01",
        "january": "01",
        "feb": "02",
        "february": "02",
        "mar": "03",
        "march": "03",
        "apr": "04",
        "april": "04",
        "may": "05",
        "jun": "06",
        "june": "06",
        "jul": "07",
        "july": "07",
        "aug": "08",
        "august": "08",
        "sep": "09",
        "sept": "09",
        "september": "09",
        "oct": "10",
        "october": "10",
        "nov": "11",
        "november": "11",
        "dec": "12",
        "december": "12",
    }
    match = re.search(
        r"\b("
        + "|".join(sorted(months, key=len, reverse=True))
        + r")[a-z]*[\s_-]+((?:19|20)\d{2})\b",
        label,
        re.IGNORECASE,
    )
    if match:
        return f"{match.group(2)}-{months[match.group(1).lower()]}"
    match = re.search(r"\b((?:19|20)\d{2})\b", label)
    return match.group(1) if match else "unknown"


def _record_id(source_id: str, url: str) -> str:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    return f"bar_exam:{source_id}:{digest}"


def _assert_metadata_only_source(source_id: str) -> None:
    assert_derived_metadata_allowed(source_id)
    try:
        assert_text_commit_allowed(source_id)
    except SourceRegistryError:
        return
    raise SourceRegistryError(f"source {source_id} unexpectedly allows full text")


def _record_from_pdf(
    config: SourceConfig,
    link: Link,
    pdf_bytes: bytes,
    retrieved_at: str,
) -> dict[str, Any]:
    label = _label(link)
    return {
        "id": _record_id(config.source_id, link.url),
        "source_id": config.source_id,
        "source_name": config.name,
        "jurisdiction": config.jurisdiction,
        "component": infer_component(label),
        "subject": infer_subject(label),
        "exam_date": infer_exam_date(label),
        "title": link.text or Path(parse.urlparse(link.url).path).name,
        "url": link.url,
        "pdf_sha256": hashlib.sha256(pdf_bytes).hexdigest(),
        "retrieved_at": retrieved_at,
        "review_status": "needs_manual_subject_review",
        "full_text_commit_allowed": False,
        "text_fields_committed": [],
        "manual_review": {
            "tort_classification": "unreviewed",
            "reviewed_by": None,
            "reviewed_at": None,
            "notes": "",
        },
    }


def build_metadata(
    *,
    source_ids: list[str] | None = None,
    fetch: Fetch = _default_fetch,
    limit: int | None = None,
    retrieved_at: str | None = None,
) -> list[dict[str, Any]]:
    selected = source_ids or list(SOURCE_CONFIGS)
    timestamp = retrieved_at or datetime.now(UTC).replace(microsecond=0).isoformat()
    records: list[dict[str, Any]] = []
    for source_id in selected:
        config = SOURCE_CONFIGS[source_id]
        _assert_metadata_only_source(source_id)
        links = _parse_links(fetch(config.index_url), config.index_url)
        for link in links:
            if not _looks_like_pdf(link.url):
                continue
            try:
                pdf_bytes = fetch(link.url)
            except RuntimeError:
                continue
            records.append(_record_from_pdf(config, link, pdf_bytes, timestamp))
            if limit is not None and len(records) >= limit:
                errors = validate_records(records)
                if errors:
                    raise ValueError("; ".join(errors))
                return records
    errors = validate_records(records)
    if errors:
        raise ValueError("; ".join(errors))
    return records


def validate_records(records: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    required = {
        "id",
        "source_id",
        "jurisdiction",
        "component",
        "subject",
        "exam_date",
        "url",
        "pdf_sha256",
        "review_status",
        "full_text_commit_allowed",
        "text_fields_committed",
        "manual_review",
    }
    for index, record in enumerate(records, start=1):
        label = str(record.get("id") or f"record[{index}]")
        missing = sorted(field for field in required if field not in record)
        if missing:
            errors.append(f"{label} missing fields: {missing}")
        record_id = str(record.get("id") or "")
        if record_id in seen:
            errors.append(f"duplicate id: {record_id}")
        seen.add(record_id)
        source_id = record.get("source_id")
        if source_id not in SOURCE_CONFIGS:
            errors.append(f"{label} has unsupported source_id {source_id!r}")
        elif record.get("jurisdiction") != SOURCE_CONFIGS[source_id].jurisdiction:
            errors.append(f"{label} jurisdiction mismatch")
        if record.get("full_text_commit_allowed") is not False:
            errors.append(f"{label} full_text_commit_allowed must be false")
        if record.get("text_fields_committed") != []:
            errors.append(f"{label} text_fields_committed must be empty")
        for field in FORBIDDEN_TEXT_FIELDS:
            if record.get(field):
                errors.append(f"{label} must not commit {field}")
        digest = record.get("pdf_sha256")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            errors.append(f"{label} pdf_sha256 must be a sha256 hex digest")
        manual_review = record.get("manual_review")
        if not isinstance(manual_review, dict):
            errors.append(f"{label} manual_review must be an object")
        elif manual_review.get("tort_classification") not in {
            "unreviewed",
            "not_tort",
            "tort",
        }:
            errors.append(f"{label} manual_review.tort_classification is invalid")
    return errors


def _load_json(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"{path} root must be a list")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--source", action="append", choices=sorted(SOURCE_CONFIGS))
    parser.add_argument("--limit", type=int)
    parser.add_argument("--validate-only", type=Path)
    args = parser.parse_args(argv)

    try:
        if args.validate_only:
            records = _load_json(args.validate_only)
            errors = validate_records(records)
            if errors:
                for item in errors:
                    print(f"ERROR: {item}", file=sys.stderr)
                return 1
            print(f"OK: {args.validate_only}")
            return 0

        records = build_metadata(source_ids=args.source, limit=args.limit)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
        print(f"OK: wrote {len(records)} records to {args.output}")
        return 0
    except (OSError, RuntimeError, ValueError, SourceRegistryError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
