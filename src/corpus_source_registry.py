"""Machine-readable corpus source registry checks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REGISTRY_PATH = Path(__file__).resolve().parents[1] / "corpus" / "source_registry.json"

REQUIRED_SOURCE_FIELDS = (
    "source_id",
    "name",
    "url",
    "jurisdiction",
    "subject",
    "source_kind",
    "license_name",
    "license_url",
    "redistribution_status",
    "commercial_use",
    "text_commit_allowed",
    "derived_metadata_allowed",
    "attribution_required",
    "terms_checked_at",
    "notes",
)


class SourceRegistryError(ValueError):
    """Raised when source registry data blocks ingestion."""


def load_source_registry(path: Path = REGISTRY_PATH) -> dict[str, dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise SourceRegistryError("source registry must be a list")

    registry: dict[str, dict[str, Any]] = {}
    for index, source in enumerate(payload):
        if not isinstance(source, dict):
            raise SourceRegistryError(f"source registry entry {index} is not an object")
        missing = [field for field in REQUIRED_SOURCE_FIELDS if field not in source]
        if missing:
            source_id = source.get("source_id", index)
            raise SourceRegistryError(f"source {source_id} missing fields: {missing}")
        source_id = source["source_id"]
        if not isinstance(source_id, str) or not source_id.strip():
            raise SourceRegistryError(f"source {index} has invalid source_id")
        if source_id in registry:
            raise SourceRegistryError(f"duplicate source_id: {source_id}")
        for field in (
            "text_commit_allowed",
            "derived_metadata_allowed",
            "attribution_required",
        ):
            if not isinstance(source[field], bool):
                raise SourceRegistryError(f"source {source_id} has non-bool {field}")
        registry[source_id] = source
    return registry


def get_source(source_id: str, path: Path = REGISTRY_PATH) -> dict[str, Any]:
    registry = load_source_registry(path)
    try:
        return registry[source_id]
    except KeyError as exc:
        raise SourceRegistryError(f"source is not registered: {source_id}") from exc


def assert_text_commit_allowed(
    source_id: str,
    path: Path = REGISTRY_PATH,
) -> dict[str, Any]:
    source = get_source(source_id, path)
    if source["text_commit_allowed"] is not True:
        raise SourceRegistryError(
            f"source {source_id} is not cleared for committed full text"
        )
    return source


def assert_derived_metadata_allowed(
    source_id: str,
    path: Path = REGISTRY_PATH,
) -> dict[str, Any]:
    source = get_source(source_id, path)
    if source["derived_metadata_allowed"] is not True:
        raise SourceRegistryError(
            f"source {source_id} is not cleared for derived metadata"
        )
    return source


def assert_records_text_commit_allowed(
    records: list[dict[str, Any]],
    path: Path = REGISTRY_PATH,
) -> None:
    for record in records:
        source = record.get("source")
        metadata = record.get("metadata")
        source_id = record.get("source_id")
        if isinstance(source, dict):
            source_id = source_id or source.get("source_id")
        if isinstance(metadata, dict):
            source_id = source_id or metadata.get("source_id")
        if not isinstance(source_id, str) or not source_id.strip():
            record_id = record.get("id", "<unknown>")
            raise SourceRegistryError(f"record {record_id} has no registered source_id")
        assert_text_commit_allowed(source_id, path)
