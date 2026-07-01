"""Local-first bronze/silver/gold corpus layering."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Literal, Optional

from pydantic import BaseModel, Field, ValidationError

from src.corpus_ingestion import (
    CorpusValidationError,
    emit_event,
    quarantine_record,
    record_source_failure,
    record_source_success,
)
from ..domain import resolve_domain_pack
from .corpus_preprocessor import (
    MIN_ENTRY_CHARS,
    SUPPORTED_RAW,
    _normalize_topics,
    extract_text,
    infer_topics_from_dir,
    normalize_text,
)

SCHEMA_VERSION = "jikai.medallion.v1"
DEFAULT_MANIFEST_PATH = Path("corpus/manifest.json")


class CorpusSource(BaseModel):
    url: str
    path: str
    source_format: str
    retrieved_at: str
    content_hash: str
    byte_size: int


class BronzeRecord(BaseModel):
    id: str
    corpus_pack_key: str
    source: CorpusSource


class SilverRecord(BaseModel):
    id: str
    text: str
    topics: list[str]
    source: CorpusSource
    provenance: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class GoldRecord(BaseModel):
    id: str
    text: str
    topics: list[str]
    corpus_pack_key: str
    jurisdiction: str
    subject: str
    subtopics: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    source: CorpusSource
    provenance: dict[str, Any] = Field(default_factory=dict)
    license: dict[str, Any] = Field(default_factory=dict)


class StageResult(BaseModel):
    stage: Literal["bronze", "silver", "gold"]
    path: str
    records_count: int
    content_hash: str
    skipped: bool
    quarantined_count: int = 0


class MedallionManifest(BaseModel):
    schema_version: str = SCHEMA_VERSION
    corpus_pack_key: str
    generated_at: str
    layers: dict[str, Any]
    records: list[BronzeRecord]


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _file_timestamp(path: Path) -> str:
    timestamp = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
    return timestamp.replace(microsecond=0).isoformat()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _json_bytes(payload: Any) -> bytes:
    return (json.dumps(payload, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def _write_json_if_changed(path: Path, payload: Any) -> tuple[bool, str]:
    data = _json_bytes(payload)
    digest = _sha256_bytes(data)
    if path.exists() and _file_sha256(path) == digest:
        return True, digest
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return False, digest


def _repo_relative(path: Path) -> str:
    try:
        return path.relative_to(Path(".").resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _safe_id_part(value: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").lower()
    return safe or "record"


def _natural_path_key(path: Path) -> list[Any]:
    parts: list[Any] = []
    for part in re.split(r"(\d+)", path.as_posix()):
        if part.isdigit():
            parts.append(int(part))
        else:
            parts.append(part.lower())
    return parts


def _default_silver_path(corpus_pack: str) -> Path:
    return Path("corpus") / "normalized" / corpus_pack / "corpus.json"


def _default_gold_path(corpus_pack: str) -> Path:
    return Path("corpus") / "labelled" / corpus_pack / "corpus.json"


def _iter_raw_files(raw_paths: Iterable[str]) -> list[Path]:
    files: list[Path] = []
    for raw_path in raw_paths:
        path = Path(raw_path)
        if path.is_file() and path.suffix.lower() in SUPPORTED_RAW:
            files.append(path)
            continue
        if not path.is_dir():
            continue
        files.extend(
            file_path
            for file_path in sorted(path.rglob("*"), key=_natural_path_key)
            if file_path.is_file() and file_path.suffix.lower() in SUPPORTED_RAW
        )
    return sorted(files, key=_natural_path_key)


def _record_id(corpus_pack: str, source_path: Path) -> str:
    stem = _safe_id_part(source_path.with_suffix("").as_posix())
    if stem.startswith("corpus_raw_"):
        stem = stem.removeprefix("corpus_raw_").strip("_")
    return f"{corpus_pack}:{stem}"


def run_bronze(
    *,
    corpus_pack: str = "sg_tort",
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
) -> StageResult:
    pack = resolve_domain_pack(corpus_pack)
    emit_event(
        "stage_started",
        source=f"{pack.key}:bronze",
        message="bronze stage started",
    )
    records = []
    for source_path in _iter_raw_files(pack.raw_paths):
        rel_path = _repo_relative(source_path)
        source = CorpusSource(
            url=f"file://{rel_path}",
            path=rel_path,
            source_format=source_path.suffix.lower().lstrip("."),
            retrieved_at=_file_timestamp(source_path),
            content_hash=_file_sha256(source_path),
            byte_size=source_path.stat().st_size,
        )
        records.append(
            BronzeRecord(
                id=_record_id(pack.key, source_path),
                corpus_pack_key=pack.key,
                source=source,
            )
        )
        record_source_success(f"{pack.key}:raw:{rel_path}", source.url)

    payload = MedallionManifest(
        corpus_pack_key=pack.key,
        generated_at=max(
            (record.source.retrieved_at for record in records),
            default=_utc_now(),
        ),
        layers={
            "bronze": {"raw_paths": list(pack.raw_paths)},
            "silver": {"path": _default_silver_path(pack.key).as_posix()},
            "gold": {"path": _default_gold_path(pack.key).as_posix()},
            "active_corpus": {"path": pack.corpus_path},
        },
        records=records,
    ).model_dump(mode="json")
    skipped, digest = _write_json_if_changed(manifest_path, payload)
    emit_event(
        "stage_completed",
        source=f"{pack.key}:bronze",
        message="bronze stage completed",
        details={"records_count": len(records), "skipped": skipped},
    )
    return StageResult(
        stage="bronze",
        path=manifest_path.as_posix(),
        records_count=len(records),
        content_hash=digest,
        skipped=skipped,
    )


def _load_bronze_records(manifest_path: Path) -> list[BronzeRecord]:
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest = MedallionManifest.model_validate(data)
    return list(manifest.records)


def _default_legacy_topic_path(corpus_pack: str) -> Optional[Path]:
    if corpus_pack == "sg_tort":
        return Path("corpus/clean/tort/corpus.json")
    return None


def _load_legacy_topics(path: Optional[Path]) -> dict[int, list[str]]:
    if path is None or not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, list):
        return {}
    topics_by_index: dict[int, list[str]] = {}
    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            continue
        topics = _normalize_topics(item.get("topics", item.get("topic")))
        if topics:
            topics_by_index[index] = topics
    return topics_by_index


def run_silver(
    *,
    corpus_pack: str = "sg_tort",
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
    output_path: Optional[Path] = None,
    legacy_topic_path: Optional[Path] = None,
    quarantine_path: Optional[Path] = None,
    min_entry_chars: int = MIN_ENTRY_CHARS,
) -> StageResult:
    if not manifest_path.exists():
        run_bronze(corpus_pack=corpus_pack, manifest_path=manifest_path)
    output_path = output_path or _default_silver_path(corpus_pack)
    quarantine_path = quarantine_path or output_path.with_name("quarantine.jsonl")
    if quarantine_path.exists():
        quarantine_path.unlink()
    emit_event(
        "stage_started",
        source=f"{corpus_pack}:silver",
        message="silver stage started",
    )
    records: list[SilverRecord] = []
    seen_text_hashes: set[str] = set()
    quarantined_count = 0
    legacy_topics = _load_legacy_topics(
        legacy_topic_path or _default_legacy_topic_path(corpus_pack)
    )
    for index, bronze in enumerate(_load_bronze_records(manifest_path)):
        if bronze.corpus_pack_key != corpus_pack:
            continue
        try:
            source_path = Path(bronze.source.path)
            text = normalize_text(extract_text(source_path))
            if len(text) < min_entry_chars:
                continue
            text_hash = _sha256_bytes(text.encode("utf-8"))
            if text_hash in seen_text_hashes:
                continue
            topics = legacy_topics.get(index) or _normalize_topics(
                infer_topics_from_dir(source_path.parent.name)
            )
            record = SilverRecord.model_validate(
                {
                    "id": bronze.id,
                    "text": text,
                    "topics": topics,
                    "source": bronze.source,
                    "provenance": {
                        "bronze_record_id": bronze.id,
                        "source_url": bronze.source.url,
                        "retrieved_at": bronze.source.retrieved_at,
                        "source_content_hash": bronze.source.content_hash,
                        "normalized_text_hash": text_hash,
                    },
                    "metadata": {
                        "source_file": source_path.as_posix(),
                        "source_dir": source_path.parent.name,
                        "medallion_layer": "silver",
                    },
                }
            )
            seen_text_hashes.add(text_hash)
            records.append(record)
            record_source_success(
                f"{corpus_pack}:silver:{bronze.id}", bronze.source.url
            )
        except (OSError, ValueError, ValidationError) as exc:
            quarantined_count += 1
            error = CorpusValidationError(str(exc))
            record_source_failure(
                f"{corpus_pack}:silver:{bronze.id}",
                bronze.source.url,
                str(error),
            )
            quarantine_record(
                quarantine_path,
                stage="silver",
                source=bronze.id,
                source_url=bronze.source.url,
                payload=bronze.model_dump(mode="json"),
                error=error,
            )
            continue

    payload = [record.model_dump(mode="json") for record in records]
    skipped, digest = _write_json_if_changed(output_path, payload)
    emit_event(
        "stage_completed",
        source=f"{corpus_pack}:silver",
        message="silver stage completed",
        details={
            "records_count": len(records),
            "quarantined_count": quarantined_count,
            "skipped": skipped,
        },
    )
    return StageResult(
        stage="silver",
        path=output_path.as_posix(),
        records_count=len(records),
        content_hash=digest,
        skipped=skipped,
        quarantined_count=quarantined_count,
    )


def _pack_manifest_license(corpus_pack: str) -> dict[str, Any]:
    pack = resolve_domain_pack(corpus_pack)
    manifest_path = Path(pack.manifest_path)
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    license_data = data.get("license", {})
    return license_data if isinstance(license_data, dict) else {}


def run_gold(
    *,
    corpus_pack: str = "sg_tort",
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
    silver_path: Optional[Path] = None,
    output_path: Optional[Path] = None,
    write_legacy_clean: bool = False,
) -> StageResult:
    pack = resolve_domain_pack(corpus_pack)
    silver_path = silver_path or _default_silver_path(corpus_pack)
    output_path = output_path or _default_gold_path(corpus_pack)
    if not silver_path.exists():
        run_silver(
            corpus_pack=corpus_pack,
            manifest_path=manifest_path,
            output_path=silver_path,
        )

    license_data = _pack_manifest_license(corpus_pack)
    silver_payload = json.loads(silver_path.read_text(encoding="utf-8"))
    records = []
    for item in silver_payload:
        silver = SilverRecord.model_validate(item)
        metadata = {
            **silver.metadata,
            "medallion_layer": "gold",
            "provenance": silver.provenance,
            "source": silver.source.model_dump(mode="json"),
        }
        records.append(
            GoldRecord(
                id=silver.id,
                text=silver.text,
                topics=silver.topics,
                corpus_pack_key=pack.key,
                jurisdiction=pack.jurisdiction_key,
                subject=pack.subject_key,
                subtopics=[],
                metadata=metadata,
                source=silver.source,
                provenance=silver.provenance,
                license=license_data,
            )
        )

    payload = [record.model_dump(mode="json") for record in records]
    skipped, digest = _write_json_if_changed(output_path, payload)
    if write_legacy_clean:
        _write_json_if_changed(Path(pack.corpus_path), payload)
    return StageResult(
        stage="gold",
        path=output_path.as_posix(),
        records_count=len(records),
        content_hash=digest,
        skipped=skipped,
    )


def run_all(corpus_pack: str = "sg_tort") -> list[StageResult]:
    return [
        run_bronze(corpus_pack=corpus_pack),
        run_silver(corpus_pack=corpus_pack),
        run_gold(corpus_pack=corpus_pack),
    ]


def _print_result(result: StageResult) -> None:
    status = "skipped" if result.skipped else "wrote"
    quarantine = (
        f", quarantined={result.quarantined_count}" if result.quarantined_count else ""
    )
    print(
        f"{result.stage}: {status} {result.records_count} records "
        f"-> {result.path} sha256={result.content_hash}{quarantine}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["bronze", "silver", "gold", "all"])
    parser.add_argument("--corpus-pack", default="sg_tort")
    parser.add_argument("--manifest-path", type=Path, default=DEFAULT_MANIFEST_PATH)
    parser.add_argument("--silver-path", type=Path)
    parser.add_argument("--gold-path", type=Path)
    parser.add_argument("--quarantine-path", type=Path)
    parser.add_argument("--write-legacy-clean", action="store_true")
    args = parser.parse_args()

    if args.stage == "bronze":
        _print_result(
            run_bronze(
                corpus_pack=args.corpus_pack,
                manifest_path=args.manifest_path,
            )
        )
    elif args.stage == "silver":
        _print_result(
            run_silver(
                corpus_pack=args.corpus_pack,
                manifest_path=args.manifest_path,
                output_path=args.silver_path,
                quarantine_path=args.quarantine_path,
            )
        )
    elif args.stage == "gold":
        _print_result(
            run_gold(
                corpus_pack=args.corpus_pack,
                manifest_path=args.manifest_path,
                silver_path=args.silver_path,
                output_path=args.gold_path,
                write_legacy_clean=args.write_legacy_clean,
            )
        )
    else:
        for result in run_all(corpus_pack=args.corpus_pack):
            _print_result(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
