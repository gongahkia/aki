"""Validate CALI metadata-only candidate records."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from src.corpus_source_registry import (
    SourceRegistryError,
    assert_derived_metadata_allowed,
    assert_text_commit_allowed,
)

DEFAULT_PATH = Path("corpus/metadata/us_tort_cali_open_education/metadata.json")
SOURCE_ID = "cali_tort_21st_century"
FORBIDDEN_TEXT_FIELDS = {
    "text",
    "fact_pattern",
    "question_prompt",
    "model_answer",
    "marking_rubric",
}


def _load_records(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("CALI metadata root must be a list")
    return payload


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _validate_record(record: dict[str, Any], index: int, errors: list[str]) -> None:
    label = str(record.get("id") or f"record[{index}]")
    required = (
        "id",
        "source_id",
        "title",
        "url",
        "topics",
        "license",
        "attribution",
        "constraints",
    )
    for field in required:
        if record.get(field) in (None, "", [], {}):
            errors.append(f"{label} missing {field}")

    if record.get("source_id") != SOURCE_ID:
        errors.append(f"{label} must use source_id {SOURCE_ID}")
    for field in FORBIDDEN_TEXT_FIELDS:
        if record.get(field):
            errors.append(f"{label} must not commit CALI {field}")

    topics = record.get("topics")
    if not isinstance(topics, list) or not all(
        isinstance(topic, str) and topic for topic in topics
    ):
        errors.append(f"{label} topics must be non-empty strings")

    license_data = _mapping(record.get("license"))
    if license_data.get("name") != "CC BY-NC-SA 4.0":
        errors.append(f"{label} must preserve CC BY-NC-SA 4.0 license")
    if license_data.get("commercial_use") != "not_allowed":
        errors.append(f"{label} must mark commercial use not_allowed")

    attribution = _mapping(record.get("attribution"))
    for field in ("work_title", "author", "publisher", "source_url", "license_url"):
        if not attribution.get(field):
            errors.append(f"{label} attribution missing {field}")

    constraints = _mapping(record.get("constraints"))
    expected_constraints = {
        "full_text_commit_allowed": False,
        "derived_metadata_allowed": True,
        "noncommercial": True,
        "share_alike": True,
        "owner_decision_required_for_text": True,
    }
    for field, expected in expected_constraints.items():
        if constraints.get(field) is not expected:
            errors.append(f"{label} constraint {field} must be {expected}")


def validate_cali_metadata(path: Path = DEFAULT_PATH) -> list[str]:
    errors: list[str] = []
    try:
        records = _load_records(path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return [f"{path}: {exc}"]

    if len(records) < 10:
        errors.append(f"{path} must contain at least 10 metadata records")
    seen: set[str] = set()
    for index, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            errors.append(f"record[{index}] must be an object")
            continue
        record_id = str(record.get("id") or "")
        if record_id in seen:
            errors.append(f"duplicate id: {record_id}")
        seen.add(record_id)
        _validate_record(record, index, errors)

    try:
        assert_derived_metadata_allowed(SOURCE_ID)
    except SourceRegistryError as exc:
        errors.append(str(exc))
    try:
        assert_text_commit_allowed(SOURCE_ID)
        errors.append(f"{SOURCE_ID} must not allow full-text commits yet")
    except SourceRegistryError:
        pass

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", type=Path, default=DEFAULT_PATH)
    args = parser.parse_args(argv)

    errors = validate_cali_metadata(args.path)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"OK: {args.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
