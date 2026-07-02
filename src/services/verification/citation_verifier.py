"""Citation-grounding verifier for structured model answers."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import structlog

from ...domain import resolve_domain_pack
from ..prompt_engineering.schemas import CitationReport, ModelAnswer

logger = structlog.get_logger(__name__)


class CitationVerifier:
    def __init__(self) -> None:
        self._corpus_indexes: dict[str, dict[str, dict[str, Any]]] = {}
        self._authorities_indexes: dict[str, dict[str, dict[str, Any]]] = {}

    async def _ensure_index(self, corpus_pack: str = "sg_tort") -> None:
        if corpus_pack in self._corpus_indexes:
            return
        from ..corpus_service import corpus_service

        entries = await corpus_service.load_corpus(corpus_pack=corpus_pack)
        self._corpus_indexes[corpus_pack] = {
            str(entry.id): {"topics": set(entry.topics), "text": entry.text}
            for entry in entries
            if entry.id
        }
        self._authorities_indexes[corpus_pack] = _load_authorities(corpus_pack)

    async def verify_model_answer(
        self, answer: ModelAnswer, corpus_pack: str = "sg_tort"
    ) -> CitationReport:
        await self._ensure_index(corpus_pack)
        corpus_index = self._corpus_indexes.get(corpus_pack, {})
        authorities_index = self._authorities_indexes.get(corpus_pack, {})
        total = verified = 0
        unknown: list[str] = []
        topic_mismatch: list[dict[str, Any]] = []
        for step in answer.steps:
            step_topics = _issue_topics(step.issue, corpus_pack=corpus_pack)
            for ref in step.citations:
                total += 1
                corpus_id = str(ref.corpus_id)
                authority_id = str(ref.authority_id or "")
                if corpus_id in corpus_index:
                    corpus_topics = set(corpus_index[corpus_id].get("topics", set()))
                    if not step_topics or step_topics & corpus_topics:
                        verified += 1
                    else:
                        topic_mismatch.append(
                            {
                                "corpus_id": corpus_id,
                                "step_topic": sorted(step_topics)[0],
                                "step_topics": sorted(step_topics),
                                "corpus_topics": sorted(corpus_topics),
                            }
                        )
                elif authority_id and authority_id in authorities_index:
                    verified += 1
                else:
                    unknown.append(corpus_id)
        accuracy = verified / total if total else 1.0
        return CitationReport(
            citation_accuracy=accuracy,
            total_citations=total,
            verified=verified,
            unknown_corpus_ids=unknown,
            topic_mismatch=topic_mismatch,
        )


def _load_authorities(corpus_pack: str) -> dict[str, dict[str, Any]]:
    auth_path = _repo_root() / "corpus" / "packs" / corpus_pack / "authorities.json"
    if not auth_path.exists():
        return {}
    try:
        data = json.loads(auth_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning(
            "Citation authorities index unavailable",
            corpus_pack=corpus_pack,
            error=str(exc),
        )
        return {}
    authorities = data.get("authorities", [])
    if not isinstance(authorities, list):
        return {}
    return {
        str(item["id"]): {
            "topics": set(item.get("topics", [])),
            "citation": item.get("citation", ""),
        }
        for item in authorities
        if isinstance(item, dict) and item.get("id")
    }


def _issue_topics(issue: str, corpus_pack: str = "sg_tort") -> set[str]:
    try:
        domain_pack = resolve_domain_pack(corpus_pack)
    except KeyError:
        domain_pack = resolve_domain_pack("sg_tort")
    lowered = issue.lower()
    matched: set[str] = set()
    definitions = domain_pack.topic_definitions or {}
    for topic in domain_pack.topic_keys:
        candidates = {topic, topic.replace("_", " ")}
        definition = definitions.get(topic)
        if definition is not None:
            candidates.add(definition.label)
            candidates.update(definition.aliases)
        for candidate in candidates:
            token = str(candidate).strip().lower()
            if token and re.search(r"(?<!\w)" + re.escape(token) + r"(?!\w)", lowered):
                matched.add(topic)
                break
    return matched


def _issue_to_topic(issue: str, corpus_pack: str = "sg_tort") -> str | None:
    topics = sorted(_issue_topics(issue, corpus_pack=corpus_pack))
    return topics[0] if topics else None


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


citation_verifier = CitationVerifier()

__all__ = ["CitationVerifier", "citation_verifier"]
