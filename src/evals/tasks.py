"""Workflow task registry for local eval runs."""

from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable
from typing import Any

from .models import EvalCase

Task = Callable[[EvalCase], Awaitable[str]]

_HYPO_GENERATOR_LOCK = asyncio.Lock()


def _topics(case: EvalCase) -> list[str]:
    raw = case.inputs.get("topics") or case.inputs.get("topic") or []
    if isinstance(raw, str):
        return [raw]
    return [str(topic) for topic in raw]


async def _retrieve_corpus_snippets(case: EvalCase, *, limit: int = 2) -> list[str]:
    from src.services.corpus_service import corpus_service

    topics = set(topic.lower() for topic in _topics(case))
    entries = await corpus_service.load_corpus(corpus_pack="sg_tort")
    scored: list[tuple[int, str]] = []
    for entry in entries:
        overlap = len(topics & {topic.lower() for topic in entry.topics})
        if overlap > 0:
            scored.append((overlap, entry.text))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [text for _, text in scored[:limit]]


async def sg_tort_hypothetical_task(case: EvalCase) -> str:
    from src.services.hypo_generator import hypo_generator

    seed = case.inputs.get("seed")
    complexity = int(case.inputs.get("complexity", 3))
    num_parties = int(case.inputs.get("num_parties", 3))
    async with _HYPO_GENERATOR_LOCK:
        if seed is not None:
            random.seed(str(seed))
        result = await hypo_generator.generate(
            topics=_topics(case),
            complexity=complexity,
            num_parties=num_parties,
            max_retries=1,
        )
    return str(result["text"])


async def sg_citation_retrieval_task(case: EvalCase) -> str:
    snippets = await _retrieve_corpus_snippets(case, limit=2)
    citation = str(case.inputs.get("citation", "")).strip()
    query = str(case.inputs.get("query", "")).strip()
    body = "\n\n".join(snippets)
    return f"{citation}\n{query}\n{body}".strip()


async def sg_statute_interpretation_mcq_task(case: EvalCase) -> str:
    choices: dict[str, Any] = dict(case.inputs.get("choices", {}))
    answer_key = str(case.inputs.get("answer_key", "")).strip()
    statute = str(case.inputs.get("statute", "")).strip()
    section = str(case.inputs.get("section", "")).strip()
    answer = str(choices.get(answer_key, ""))
    section_text = f", s {section}" if section else ""
    return f"Answer: {answer_key}. {answer} ({statute}{section_text})."


async def sg_factual_reasoning_task(case: EvalCase) -> str:
    facts = case.inputs.get("facts", [])
    if isinstance(facts, str):
        facts = [facts]
    issues = _topics(case) or list(case.inputs.get("issues", []))
    reasoning_terms = case.inputs.get("reasoning_terms") or [
        "duty",
        "breach",
        "causation",
        "damage",
    ]
    return (
        "Facts: "
        + " ".join(str(fact) for fact in facts)
        + "\nIssues: "
        + ", ".join(str(issue) for issue in issues)
        + "\nReasoning: "
        + ", ".join(str(term) for term in reasoning_terms)
    )


TASKS: dict[str, Task] = {
    "sg_tort_hypothetical": sg_tort_hypothetical_task,
    "sg_citation_retrieval": sg_citation_retrieval_task,
    "sg_statute_interpretation_mcq": sg_statute_interpretation_mcq_task,
    "sg_factual_reasoning": sg_factual_reasoning_task,
}

__all__ = [
    "TASKS",
    "Task",
    "sg_tort_hypothetical_task",
    "sg_citation_retrieval_task",
    "sg_statute_interpretation_mcq_task",
    "sg_factual_reasoning_task",
]
