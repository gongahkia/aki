"""Synthetic SG Tort corpus expansion with review gating."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, Optional

from ..domain import canonicalize_topic, resolve_domain_pack
from ..domain.templates import available_templates, load_topic_template

DEFAULT_NOVELTY_THRESHOLD = 0.55


class SyntheticExpansionError(Exception):
    """Raised when synthetic corpus generation cannot proceed safely."""


@dataclass(frozen=True)
class SyntheticExpansionResult:
    output_path: str
    records_count: int
    rejected_count: int
    max_similarity: float


@dataclass(frozen=True)
class PromotionResult:
    output_path: str
    promoted_count: int
    skipped_count: int


def build_synthetic_review_queue(
    *,
    corpus_pack: str = "sg_tort",
    topics: Optional[Iterable[str]] = None,
    output_path: Optional[Path] = None,
    existing_corpus_paths: Optional[Iterable[Path]] = None,
    max_per_topic: int = 1,
    novelty_threshold: float = DEFAULT_NOVELTY_THRESHOLD,
) -> SyntheticExpansionResult:
    """Write generated records to a human review queue, not gold corpus."""
    pack = resolve_domain_pack(corpus_pack)
    output_path = output_path or _default_review_queue_path(pack.key)
    topic_keys = _selected_topics(topics)
    authorities = _load_authorities(pack.manifest_path)
    existing_texts = _load_existing_texts(pack.key, existing_corpus_paths)
    records: list[dict[str, Any]] = []
    rejected_count = 0
    max_similarity_seen = 0.0

    for topic in topic_keys:
        template = load_topic_template(topic)
        if not template:
            continue
        topic_authorities = _authority_sources_for_topic(authorities, topic)
        if not topic_authorities:
            raise SyntheticExpansionError(
                f"No authority source found for synthetic topic: {topic}"
            )
        patterns = _string_items(template.get("scenario_patterns"))[:max_per_topic]
        for index, pattern in enumerate(patterns):
            authority = topic_authorities[index % len(topic_authorities)]
            record = _build_record(
                corpus_pack=pack.key,
                jurisdiction=pack.jurisdiction_key,
                subject=pack.subject_key,
                topic=topic,
                template=template,
                pattern=pattern,
                authority=authority,
                index=index,
                novelty_threshold=novelty_threshold,
                existing_texts=existing_texts,
            )
            novelty = record["metadata"]["novelty"]
            max_similarity_seen = max(max_similarity_seen, novelty["max_similarity"])
            if not novelty["passed"]:
                rejected_count += 1
                continue
            records.append(record)
            existing_texts.append(record["text"])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(records, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return SyntheticExpansionResult(
        output_path=output_path.as_posix(),
        records_count=len(records),
        rejected_count=rejected_count,
        max_similarity=round(max_similarity_seen, 4),
    )


def mark_record_reviewed(
    record: dict[str, Any],
    *,
    reviewer: str,
    reviewed_at: Optional[str] = None,
) -> dict[str, Any]:
    """Mark one human-reviewed synthetic record as eligible for gold promotion."""
    reviewed_at = reviewed_at or _utc_now()
    updated = dict(record)
    metadata = dict(updated.get("metadata", {}))
    source_exam_context = dict(updated.get("source_exam_context", {}))
    metadata.update(
        {
            "synthetic_status": "generated_reviewed",
            "generated_reviewed": True,
            "review_status": "reviewed",
            "reviewed_by": reviewer,
            "reviewed_at": reviewed_at,
            "retrieval_eligible": True,
            "requires_human_review": False,
        }
    )
    source_exam_context.update(
        {
            "synthetic_status": "generated_reviewed",
            "generated_reviewed": True,
            "review_status": "reviewed",
            "reviewed_by": reviewer,
            "reviewed_at": reviewed_at,
        }
    )
    updated["metadata"] = metadata
    updated["source_exam_context"] = source_exam_context
    updated["updated_at"] = reviewed_at
    return updated


def promote_reviewed_synthetic_records(
    *,
    review_queue_path: Path,
    gold_path: Path,
    output_path: Optional[Path] = None,
) -> PromotionResult:
    """Append only human-reviewed synthetic records to gold corpus."""
    output_path = output_path or gold_path
    queue_records = _load_json_list(review_queue_path)
    gold_records = _load_json_list(gold_path) if gold_path.exists() else []
    existing_ids = {
        str(item.get("id")) for item in gold_records if isinstance(item, dict)
    }
    promoted: list[dict[str, Any]] = []

    for item in queue_records:
        if not isinstance(item, dict):
            continue
        if not _is_generated_reviewed(item):
            continue
        item_id = str(item.get("id"))
        if item_id in existing_ids:
            continue
        promoted.append(item)
        existing_ids.add(item_id)

    payload = gold_records + promoted
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return PromotionResult(
        output_path=output_path.as_posix(),
        promoted_count=len(promoted),
        skipped_count=len(queue_records) - len(promoted),
    )


def text_similarity(left: str, right: str) -> float:
    left_tokens = set(_tokens(left))
    right_tokens = set(_tokens(right))
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def _build_record(
    *,
    corpus_pack: str,
    jurisdiction: str,
    subject: str,
    topic: str,
    template: dict[str, Any],
    pattern: str,
    authority: dict[str, Any],
    index: int,
    novelty_threshold: float,
    existing_texts: list[str],
) -> dict[str, Any]:
    label = str(template.get("label") or topic.replace("_", " ").title())
    legal_tests = _string_items(template.get("legal_tests"))
    defences = _string_items(template.get("defences"))
    rule = str(authority.get("headnote") or authority.get("notes") or "").strip()
    citation = str(authority["citation"])
    fact_pattern = (
        f"In Singapore, {pattern[0].lower()}{pattern[1:]}. "
        f"The dispute raises {label.lower()} and asks whether the claimant can "
        "recover damages in tort."
    )
    question_prompt = f"Advise the parties on their rights and remedies under Singapore tort law, citing {citation}."
    model_answer = (
        f"A strong answer should cite {citation}. The rule source states: {rule} "
        "Apply the rule to duty, breach, causation, remoteness, defences, and remedies."
    )
    text = f"{fact_pattern}\n\n{question_prompt}"
    max_similarity = max(
        (text_similarity(text, existing) for existing in existing_texts), default=0.0
    )
    now = _utc_now()
    digest = _digest_id(f"{corpus_pack}:{topic}:{index}:{pattern}:{citation}")
    authority_source = _authority_snapshot(authority)
    return {
        "id": f"{corpus_pack}:synthetic:{topic}:{digest}",
        "text": text,
        "topics": [topic],
        "question_prompt": question_prompt,
        "fact_pattern": fact_pattern,
        "issues_expected": legal_tests[:3],
        "model_answer": model_answer,
        "marking_rubric": {
            "rule_sources": [authority_source],
            "issue_checks": legal_tests[:3],
            "defence_checks": defences[:2],
        },
        "difficulty": "intermediate",
        "answer_visibility": "after_attempt",
        "source_exam_context": {
            "source_type": "repo_authored_synthetic",
            "synthetic_status": "generated_pending_review",
            "generated_reviewed": False,
            "review_status": "pending",
            "authority_source_ids": [authority_source["id"]],
        },
        "corpus_pack_key": corpus_pack,
        "jurisdiction": jurisdiction,
        "subject": subject,
        "subtopics": [],
        "metadata": {
            "synthetic_status": "generated_pending_review",
            "generated_reviewed": False,
            "review_status": "pending",
            "requires_human_review": True,
            "retrieval_eligible": False,
            "generator": "repo_topic_template_v1",
            "template_topic": topic,
            "authority_sources": [authority_source],
            "novelty": {
                "max_similarity": round(max_similarity, 4),
                "threshold": novelty_threshold,
                "passed": max_similarity < novelty_threshold,
            },
        },
        "created_at": now,
        "updated_at": now,
    }


def _selected_topics(topics: Optional[Iterable[str]]) -> list[str]:
    if topics is None:
        return sorted(available_templates())
    selected = []
    for topic in topics:
        canonical = canonicalize_topic(str(topic))
        if canonical and canonical not in selected:
            selected.append(canonical)
    return selected


def _load_authorities(manifest_path: str) -> list[dict[str, Any]]:
    manifest = _load_json_object(Path(manifest_path))
    authorities_path = manifest.get("authorities_path")
    if not authorities_path:
        raise SyntheticExpansionError("Pack manifest does not declare authorities_path")
    payload = _load_json_object(Path(str(authorities_path)))
    authorities = payload.get("authorities", [])
    statutes = payload.get("statutes", [])
    items = []
    for item in list(authorities) + list(statutes):
        if isinstance(item, dict) and item.get("id") and item.get("citation"):
            items.append(item)
    return items


def _authority_sources_for_topic(
    authorities: list[dict[str, Any]], topic: str
) -> list[dict[str, Any]]:
    matches = []
    for authority in authorities:
        topics = [canonicalize_topic(str(item)) for item in authority.get("topics", [])]
        if topic in topics:
            matches.append(authority)
    return matches


def _authority_snapshot(authority: dict[str, Any]) -> dict[str, str]:
    return {
        "id": str(authority["id"]),
        "citation": str(authority["citation"]),
        "rule": str(authority.get("headnote") or authority.get("notes") or ""),
    }


def _load_existing_texts(
    corpus_pack: str, existing_corpus_paths: Optional[Iterable[Path]]
) -> list[str]:
    if existing_corpus_paths is None:
        pack = resolve_domain_pack(corpus_pack)
        paths = [Path(pack.corpus_path)]
        paths.extend(Path(path) for path in pack.supplemental_corpus_paths)
    else:
        paths = list(existing_corpus_paths)
    texts: list[str] = []
    for path in paths:
        if not path.exists():
            continue
        for item in _load_json_list(path):
            if isinstance(item, dict):
                text = str(item.get("text", ""))
                if text:
                    texts.append(text)
    return texts


def _is_generated_reviewed(record: dict[str, Any]) -> bool:
    metadata = record.get("metadata", {})
    context = record.get("source_exam_context", {})
    if not isinstance(metadata, dict):
        metadata = {}
    if not isinstance(context, dict):
        context = {}
    return (
        metadata.get("synthetic_status") == "generated_reviewed"
        and metadata.get("generated_reviewed") is True
        and metadata.get("review_status") == "reviewed"
        and context.get("generated_reviewed") is True
    )


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SyntheticExpansionError(f"Unable to load JSON object: {path}") from exc
    if not isinstance(payload, dict):
        raise SyntheticExpansionError(f"JSON root must be an object: {path}")
    return payload


def _load_json_list(path: Path) -> list[Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SyntheticExpansionError(f"Unable to load JSON list: {path}") from exc
    if not isinstance(payload, list):
        raise SyntheticExpansionError(f"JSON root must be a list: {path}")
    return payload


def _default_review_queue_path(corpus_pack: str) -> Path:
    return Path("corpus") / "generated" / corpus_pack / "review_queue.json"


def _string_items(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _tokens(value: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", value.lower())


def _digest_id(value: str) -> str:
    import hashlib

    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:10]


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser("generate")
    generate.add_argument("--corpus-pack", default="sg_tort")
    generate.add_argument("--topic", action="append", dest="topics")
    generate.add_argument("--output-path", type=Path)
    generate.add_argument("--max-per-topic", type=int, default=1)
    generate.add_argument(
        "--novelty-threshold", type=float, default=DEFAULT_NOVELTY_THRESHOLD
    )

    promote = subparsers.add_parser("promote")
    promote.add_argument("--review-queue-path", type=Path, required=True)
    promote.add_argument("--gold-path", type=Path, required=True)
    promote.add_argument("--output-path", type=Path)

    args = parser.parse_args()
    if args.command == "generate":
        result = build_synthetic_review_queue(
            corpus_pack=args.corpus_pack,
            topics=args.topics,
            output_path=args.output_path,
            max_per_topic=args.max_per_topic,
            novelty_threshold=args.novelty_threshold,
        )
        print(json.dumps(result.__dict__, sort_keys=True))
        return 0
    promotion_result = promote_reviewed_synthetic_records(
        review_queue_path=args.review_queue_path,
        gold_path=args.gold_path,
        output_path=args.output_path,
    )
    print(json.dumps(promotion_result.__dict__, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
