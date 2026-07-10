"""Audit corpus records for measurable coverage and schema quality."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from src.domain.packs import resolve_domain_pack

REQUIRED_FIELDS = (
    "source",
    "provenance",
    "license",
    "jurisdiction",
    "subject",
    "topics",
)
EXAM_CUE_RE = re.compile(
    r"\b(advise|discuss|you may assume|model answer|problem question|essay|"
    r"hypothetical|irac)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class AuditRecord:
    path: Path
    index: int
    record_id: str
    pack: str
    kind: str
    exam_like: bool
    has_answer: bool
    has_rubric: bool


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _string(value: Any) -> str:
    return str(value or "").strip()


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _pack_from_path(path: Path) -> str:
    parts = set(path.parts)
    if "us_tort" in parts:
        return "us_tort"
    if "uk_tort" in parts:
        return "uk_tort"
    return "sg_tort"


def _pack_key(path: Path, record: dict[str, Any]) -> str:
    metadata = _mapping(record.get("metadata"))
    return (
        _string(record.get("corpus_pack_key"))
        or _string(record.get("corpus_pack"))
        or _string(metadata.get("corpus_pack_key"))
        or _string(metadata.get("corpus_pack"))
        or _pack_from_path(path)
    )


def _source_type(record: dict[str, Any]) -> str:
    source = _mapping(record.get("source"))
    metadata = _mapping(record.get("metadata"))
    metadata_source = _mapping(metadata.get("source"))
    return (
        _string(source.get("source_format"))
        or _string(source.get("source_type"))
        or _string(source.get("access"))
        or _string(metadata_source.get("source_format"))
        or "unknown"
    )


def _license_name(record: dict[str, Any]) -> str:
    license_data = _mapping(record.get("license"))
    return (
        _string(license_data.get("name"))
        or _string(license_data.get("license_name"))
        or "unknown"
    )


def _has_answer(record: dict[str, Any]) -> bool:
    fields = ("model_answer", "answer", "issues_expected")
    return any(bool(record.get(field)) for field in fields)


def _has_rubric(record: dict[str, Any]) -> bool:
    return bool(record.get("marking_rubric") or record.get("rubric"))


def _record_text(record: dict[str, Any]) -> str:
    values = [
        record.get("question_prompt"),
        record.get("fact_pattern"),
        record.get("text"),
        record.get("model_answer"),
    ]
    return "\n".join(_string(value) for value in values if _string(value))


def _is_exam_like(record: dict[str, Any]) -> bool:
    if _has_case_law_signal(record):
        return False
    if record.get("question_prompt") or record.get("fact_pattern"):
        return True
    return bool(EXAM_CUE_RE.search(_record_text(record)))


def _has_case_law_signal(record: dict[str, Any]) -> bool:
    metadata = _mapping(record.get("metadata"))
    source = _mapping(record.get("source"))
    source_format = _source_type(record)

    if any(
        metadata.get(key)
        for key in ("case_name", "neutral_citation", "citations", "court")
    ):
        return True
    if source_format in {"cap_static_json", "tna_legaldocml_xml"}:
        return True
    if "case.law" in _string(
        source.get("url")
    ) or "caselaw.nationalarchives" in _string(source.get("url")):
        return True
    return False


def _record_kind(record: dict[str, Any]) -> str:
    text = _record_text(record)

    if _has_case_law_signal(record):
        return "case_law"
    if record.get("model_answer") and not (
        record.get("fact_pattern") or record.get("text")
    ):
        return "model_answer"
    if _is_exam_like(record):
        return "hypo"
    if re.search(
        r"\b(doctrine|commentary|overview|chapter|guide)\b", text, re.IGNORECASE
    ):
        return "doctrinal_reference"
    return "unknown"


def _record_label(path: Path, index: int, record: dict[str, Any]) -> str:
    return f"{path}:{index}:{_string(record.get('id')) or '<missing-id>'}"


def _validate_required(
    path: Path, index: int, record: dict[str, Any], errors: list[str]
) -> None:
    label = _record_label(path, index, record)
    for field in REQUIRED_FIELDS:
        value = record.get(field)
        if value in (None, "", []):
            errors.append(f"{label} missing required field '{field}'")
    if not isinstance(record.get("topics"), list):
        errors.append(f"{label} field 'topics' must be a list")


def _validate_topics(
    path: Path,
    index: int,
    record: dict[str, Any],
    pack_key: str,
    errors: list[str],
) -> list[str]:
    label = _record_label(path, index, record)
    try:
        pack = resolve_domain_pack(pack_key)
    except KeyError:
        errors.append(f"{label} references unknown corpus pack '{pack_key}'")
        return []

    canonical_topics = set(pack.topic_keys)
    valid_topics: list[str] = []
    for raw_topic in _list(record.get("topics")):
        topic = _string(raw_topic)
        canonical = pack.canonicalize_topic(topic)
        if topic != canonical:
            errors.append(
                f"{label} topic '{topic}' is not canonical; expected '{canonical}'"
            )
            continue
        if canonical not in canonical_topics:
            errors.append(f"{label} topic '{topic}' is not in {pack_key} taxonomy")
            continue
        valid_topics.append(topic)
    return valid_topics


def _iter_corpus_files(root: Path) -> Iterable[Path]:
    yield from sorted((root / "corpus").glob("**/corpus.json"))


def audit(root: Path) -> tuple[list[AuditRecord], dict[str, Counter[str]], list[str]]:
    errors: list[str] = []
    records: list[AuditRecord] = []
    counts: dict[str, Counter[str]] = defaultdict(Counter)

    for path in _iter_corpus_files(root):
        try:
            payload = _load_json(path)
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{path}: cannot load JSON: {exc}")
            continue
        if not isinstance(payload, list):
            errors.append(f"{path}: corpus root must be a list")
            continue

        for index, raw_record in enumerate(payload, start=1):
            if not isinstance(raw_record, dict):
                errors.append(f"{path}:{index}: record must be an object")
                continue
            record = raw_record
            pack_key = _pack_key(path, record)
            _validate_required(path, index, record, errors)
            topics = _validate_topics(path, index, record, pack_key, errors)

            kind = _record_kind(record)
            exam_like = _is_exam_like(record)
            has_answer = _has_answer(record)
            has_rubric = _has_rubric(record)
            record_id = _string(record.get("id")) or f"{path.stem}_{index}"
            records.append(
                AuditRecord(
                    path=path,
                    index=index,
                    record_id=record_id,
                    pack=pack_key,
                    kind=kind,
                    exam_like=exam_like,
                    has_answer=has_answer,
                    has_rubric=has_rubric,
                )
            )

            counts["pack"][pack_key] += 1
            counts["corpus_file"][str(path.relative_to(root))] += 1
            counts["source_type"][_source_type(record)] += 1
            counts["license"][_license_name(record)] += 1
            counts["record_kind"][kind] += 1
            counts["exam_likeness"]["yes" if exam_like else "no"] += 1
            counts["answer_availability"]["yes" if has_answer else "no"] += 1
            counts["rubric_availability"]["yes" if has_rubric else "no"] += 1
            counts["answer_rubric"][
                f"answer={'yes' if has_answer else 'no'},rubric={'yes' if has_rubric else 'no'}"
            ] += 1
            for topic in topics:
                counts[f"topic:{pack_key}"][topic] += 1

    return records, counts, errors


def _print_counter(title: str, counter: Counter[str]) -> None:
    print(title)
    if not counter:
        print("  <none>")
        return
    for key, count in sorted(counter.items()):
        print(f"  {key}: {count}")


def _print_report(records: list[AuditRecord], counts: dict[str, Counter[str]]) -> None:
    print("Corpus audit")
    print(f"Records: {len(records)}")
    print()
    _print_counter("By pack", counts["pack"])
    _print_counter("By corpus file", counts["corpus_file"])
    _print_counter("By source type", counts["source_type"])
    _print_counter("By license", counts["license"])
    _print_counter("By record kind", counts["record_kind"])
    _print_counter("Exam likeness", counts["exam_likeness"])
    _print_counter("Answer availability", counts["answer_availability"])
    _print_counter("Rubric availability", counts["rubric_availability"])
    _print_counter("Answer/rubric matrix", counts["answer_rubric"])
    for key in sorted(counts):
        if key.startswith("topic:"):
            _print_counter(f"By topic ({key.removeprefix('topic:')})", counts[key])

    print("Record flags")
    for record in records:
        print(
            f"  {record.pack} {record.record_id}: kind={record.kind} "
            f"exam_like={'yes' if record.exam_like else 'no'} "
            f"answer={'yes' if record.has_answer else 'no'} "
            f"rubric={'yes' if record.has_rubric else 'no'} "
            f"path={record.path}:{record.index}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)

    records, counts, errors = audit(args.root)
    _print_report(records, counts)
    if errors:
        print()
        print("Errors")
        for error in errors:
            print(f"  {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
