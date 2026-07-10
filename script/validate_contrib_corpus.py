"""Validate authored corpus contributions."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from src.corpus_source_registry import (
    SourceRegistryError,
    assert_records_text_commit_allowed,
)
from src.domain import resolve_domain_pack

DEFAULT_PATH = Path("corpus/contrib/sg_tort/corpus.json")
SOURCE_ID = "sg_tort_authored_contrib"
MIN_RECORDS = 80
MIN_PER_CORE_TOPIC = 5
CORE_TOPICS = (
    "negligence",
    "duty_of_care",
    "standard_of_care",
    "causation",
    "remoteness",
    "contributory_negligence",
    "consent_defence",
    "illegality_defence",
    "vicarious_liability",
    "private_nuisance",
    "trespass_to_land",
    "defamation",
)
INTENTIONAL_TOPICS = {
    "assault",
    "battery",
    "false_imprisonment",
    "intentional_infliction_of_mental_harm",
}
BLOCKED_TEXT_MARKERS = (
    "past exam",
    "real exam",
    "actual exam",
    "bar exam",
    "university exam",
    "tutorial handout",
)


def _load_records(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("contribution corpus root must be a list")
    return payload


def _string(value: Any) -> str:
    return str(value or "").strip()


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _certification(record: dict[str, Any]) -> dict[str, Any]:
    context = _mapping(record.get("source_exam_context"))
    return _mapping(context.get("certification"))


def _validate_record(
    record: dict[str, Any],
    index: int,
    canonical_topics: set[str],
    errors: list[str],
) -> list[str]:
    label = _string(record.get("id")) or f"record[{index}]"
    required = (
        "id",
        "text",
        "topics",
        "question_prompt",
        "fact_pattern",
        "difficulty",
        "answer_visibility",
        "source_exam_context",
        "source",
        "provenance",
        "license",
    )
    for field in required:
        if record.get(field) in (None, "", [], {}):
            errors.append(f"{label} missing {field}")

    topics = [_string(topic) for topic in _list(record.get("topics")) if _string(topic)]
    for topic in topics:
        if topic not in canonical_topics:
            errors.append(f"{label} has non-canonical SG Tort topic: {topic}")

    if not record.get("issues_expected") and not record.get("model_answer"):
        errors.append(f"{label} must include issues_expected or model_answer")
    if record.get("answer_visibility") != "hidden":
        errors.append(f"{label} must keep answer_visibility hidden")
    if _string(record.get("fact_pattern")) == _string(record.get("model_answer")):
        errors.append(f"{label} must separate fact_pattern from model_answer")

    text_for_blocklist = " ".join(
        [
            _string(record.get("text")),
            _string(record.get("question_prompt")),
            _string(record.get("fact_pattern")),
        ]
    ).lower()
    for marker in BLOCKED_TEXT_MARKERS:
        if marker in text_for_blocklist:
            errors.append(f"{label} contains blocked source marker: {marker}")

    source = _mapping(record.get("source"))
    if source.get("source_id") != SOURCE_ID:
        errors.append(f"{label} must use source_id {SOURCE_ID}")

    cert = _certification(record)
    for field in (
        "originality_certified",
        "permission_certified",
        "no_real_exam_text",
        "no_personal_data",
    ):
        if cert.get(field) is not True:
            errors.append(f"{label} missing certification flag {field}=true")

    return topics


def validate_contrib_corpus(path: Path = DEFAULT_PATH) -> list[str]:
    errors: list[str] = []
    try:
        records = _load_records(path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return [f"{path}: {exc}"]

    if len(records) < MIN_RECORDS:
        errors.append(f"{path} must contain at least {MIN_RECORDS} records")

    pack = resolve_domain_pack("sg_tort")
    canonical_topics = set(pack.topic_keys)
    ids: set[str] = set()
    coverage: Counter[str] = Counter()

    for index, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            errors.append(f"record[{index}] must be an object")
            continue
        record_id = _string(record.get("id"))
        if record_id in ids:
            errors.append(f"duplicate id: {record_id}")
        ids.add(record_id)
        if not record_id.startswith("sg_tort:contrib_"):
            errors.append(f"{record_id or index} must use sg_tort:contrib_ id prefix")

        topics = _validate_record(record, index, canonical_topics, errors)
        for topic in set(topics):
            coverage[topic] += 1
        if set(topics) & INTENTIONAL_TOPICS:
            coverage["intentional_torts"] += 1

    for topic in CORE_TOPICS:
        if coverage[topic] < MIN_PER_CORE_TOPIC:
            errors.append(
                f"core topic {topic} has {coverage[topic]} records; "
                f"expected {MIN_PER_CORE_TOPIC}"
            )
    if coverage["intentional_torts"] < MIN_PER_CORE_TOPIC:
        errors.append(
            "core topic intentional_torts has "
            f"{coverage['intentional_torts']} records; expected {MIN_PER_CORE_TOPIC}"
        )

    try:
        assert_records_text_commit_allowed(records)
    except SourceRegistryError as exc:
        errors.append(str(exc))

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", type=Path, default=DEFAULT_PATH)
    args = parser.parse_args(argv)

    errors = validate_contrib_corpus(args.path)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"OK: {args.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
