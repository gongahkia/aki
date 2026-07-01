"""Validate a Jikai corpus-pack manifest.

Usage:
    python3 script/validate_corpus_pack.py corpus/packs/sg_tort/manifest.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


KEY_RE = re.compile(r"^[a-z][a-z0-9_]*$")
SCHEMA_VERSION = "1.0"
REDISTRIBUTION_STATUSES = {
    "allowed",
    "restricted",
    "unknown",
    "bundled_fixture",
}


def _is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _require_mapping(
    value: Any,
    name: str,
    errors: list[str],
) -> dict[str, Any]:
    if not isinstance(value, dict):
        errors.append(f"{name} must be an object")
        return {}
    return value


def _require_list(value: Any, name: str, errors: list[str]) -> list[Any]:
    if not isinstance(value, list) or not value:
        errors.append(f"{name} must be a non-empty array")
        return []
    return value


def _require_string(obj: dict[str, Any], key: str, name: str, errors: list[str]) -> None:
    if not _is_non_empty_string(obj.get(key)):
        errors.append(f"{name}.{key} must be a non-empty string")


def _check_path(repo_root: Path, rel_path: Any, name: str, errors: list[str]) -> None:
    if not _is_non_empty_string(rel_path):
        errors.append(f"{name} must be a non-empty string path")
        return
    path_text = str(rel_path)
    if path_text.startswith(("http://", "https://", "file://")):
        if path_text.startswith("file://"):
            file_path = repo_root / path_text.removeprefix("file://")
            if not file_path.exists():
                errors.append(f"{name} points to missing file URL path: {file_path}")
        return
    path = repo_root / path_text
    if not path.exists():
        errors.append(f"{name} points to missing path: {path}")


def _validate_sources(data: dict[str, Any], errors: list[str]) -> None:
    sources = _require_list(data.get("sources"), "sources", errors)
    for index, source_value in enumerate(sources):
        name = f"sources[{index}]"
        source = _require_mapping(source_value, name, errors)
        for key in ("name", "source_format", "access", "notes"):
            _require_string(source, key, name, errors)
        if "url" not in source:
            errors.append(f"{name}.url is required")
        elif source["url"] is not None and not _is_non_empty_string(source["url"]):
            errors.append(f"{name}.url must be a string or null")
        if "terms_url" not in source:
            errors.append(f"{name}.terms_url is required")
        elif source["terms_url"] is not None and not _is_non_empty_string(
            source["terms_url"]
        ):
            errors.append(f"{name}.terms_url must be a string or null")


def _validate_taxonomy(data: dict[str, Any], errors: list[str]) -> None:
    taxonomy = _require_mapping(data.get("taxonomy"), "taxonomy", errors)
    _require_string(taxonomy, "version", "taxonomy", errors)
    topics = _require_list(taxonomy.get("topics"), "taxonomy.topics", errors)
    seen: set[str] = set()
    for index, topic_value in enumerate(topics):
        name = f"taxonomy.topics[{index}]"
        topic = _require_mapping(topic_value, name, errors)
        for key in ("key", "label", "category", "description"):
            _require_string(topic, key, name, errors)
        key = topic.get("key")
        if _is_non_empty_string(key):
            if not KEY_RE.match(key):
                errors.append(f"{name}.key must be lower snake case")
            if key in seen:
                errors.append(f"{name}.key is duplicated: {key}")
            seen.add(key)
        if not isinstance(topic.get("aliases"), list):
            errors.append(f"{name}.aliases must be an array")
        if not isinstance(topic.get("subtopics"), list):
            errors.append(f"{name}.subtopics must be an array")
            continue
        for sub_index, subtopic_value in enumerate(topic["subtopics"]):
            sub_name = f"{name}.subtopics[{sub_index}]"
            subtopic = _require_mapping(subtopic_value, sub_name, errors)
            for key in ("key", "label"):
                _require_string(subtopic, key, sub_name, errors)
            sub_key = subtopic.get("key")
            if _is_non_empty_string(sub_key) and not KEY_RE.match(sub_key):
                errors.append(f"{sub_name}.key must be lower snake case")


def validate_manifest(path: Path, repo_root: Path) -> list[str]:
    errors: list[str] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]

    if not isinstance(data, dict):
        return ["manifest root must be an object"]

    for key in ("schema_version", "key", "display_name", "status"):
        _require_string(data, key, "manifest", errors)

    if data.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"manifest.schema_version must be {SCHEMA_VERSION}")
    if _is_non_empty_string(data.get("key")) and not KEY_RE.match(str(data["key"])):
        errors.append("manifest.key must be lower snake case")

    jurisdiction = _require_mapping(data.get("jurisdiction"), "jurisdiction", errors)
    for key in ("code", "name", "legal_system"):
        _require_string(jurisdiction, key, "jurisdiction", errors)

    subject = _require_mapping(data.get("subject"), "subject", errors)
    for key in ("key", "name"):
        _require_string(subject, key, "subject", errors)
    if _is_non_empty_string(subject.get("key")) and not KEY_RE.match(subject["key"]):
        errors.append("subject.key must be lower snake case")

    corpus = _require_mapping(data.get("corpus"), "corpus", errors)
    for key in ("clean_path", "record_format", "id_prefix"):
        _require_string(corpus, key, "corpus", errors)
    _check_path(repo_root, corpus.get("clean_path"), "corpus.clean_path", errors)
    raw_paths = _require_list(corpus.get("raw_paths"), "corpus.raw_paths", errors)
    for index, raw_path in enumerate(raw_paths):
        _check_path(repo_root, raw_path, f"corpus.raw_paths[{index}]", errors)

    _validate_sources(data, errors)

    license_data = _require_mapping(data.get("license"), "license", errors)
    _require_string(license_data, "name", "license", errors)
    _require_string(license_data, "redistribution_status", "license", errors)
    _require_string(license_data, "terms_notes", "license", errors)
    if license_data.get("redistribution_status") not in REDISTRIBUTION_STATUSES:
        errors.append(
            "license.redistribution_status must be one of "
            + ", ".join(sorted(REDISTRIBUTION_STATUSES))
        )

    _validate_taxonomy(data, errors)

    pipeline = _require_mapping(data.get("pipeline"), "pipeline", errors)
    for key in ("ingestion_command", "cleaner_command"):
        _require_string(pipeline, key, "pipeline", errors)

    validation = _require_mapping(data.get("validation"), "validation", errors)
    count_min = validation.get("expected_record_count_min")
    if not isinstance(count_min, int) or count_min < 0:
        errors.append("validation.expected_record_count_min must be a non-negative int")
    required_fields = validation.get("required_record_fields")
    if not isinstance(required_fields, list) or not required_fields:
        errors.append("validation.required_record_fields must be a non-empty array")
    elif not all(_is_non_empty_string(field) for field in required_fields):
        errors.append("validation.required_record_fields must contain strings")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    args = parser.parse_args()

    errors = validate_manifest(args.manifest, args.repo_root)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"OK: {args.manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
