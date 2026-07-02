"""Workflow task registry for local eval runs."""

from __future__ import annotations

import asyncio
import random
import re
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


def _entry_to_document(entry: Any) -> dict[str, Any]:
    return {
        "id": getattr(entry, "id", None),
        "text": getattr(entry, "text", ""),
        "topics": list(getattr(entry, "topics", []) or []),
        "corpus_pack_key": getattr(entry, "corpus_pack_key", "sg_tort"),
        "jurisdiction": getattr(entry, "jurisdiction", "sg"),
        "subject": getattr(entry, "subject", "tort"),
        "subtopics": list(getattr(entry, "subtopics", []) or []),
        "metadata": dict(getattr(entry, "metadata", {}) or {}),
    }


def _build_request_from_case(case: EvalCase):
    from src.services.hypothetical_service import GenerationRequest

    inputs = case.inputs
    metadata = case.metadata
    subject = str(metadata.get("subject", metadata.get("law_domain", "tort")))
    prefs = dict(inputs.get("user_preferences", {}) or {})
    prefs.setdefault("include_model_answer", True)
    prefs.setdefault("disable_cache", True)
    return GenerationRequest(
        topics=_topics(case),
        corpus_pack=str(metadata.get("corpus_pack", "sg_tort")),
        jurisdiction=str(metadata.get("jurisdiction", "sg")),
        subject=subject,
        law_domain=subject,
        subtopics=list(metadata.get("subtopics", []) or []),
        number_parties=int(inputs.get("number_parties", inputs.get("num_parties", 3))),
        complexity_level=str(
            inputs.get("complexity_level", inputs.get("complexity", 3))
        ),
        sample_size=int(inputs.get("top_k", inputs.get("sample_size", 5))),
        user_preferences=prefs,
        method=str(inputs.get("method", "hybrid")),
        provider=inputs.get("provider"),
        model=inputs.get("model"),
        include_analysis=bool(inputs.get("include_analysis", False)),
        correlation_id=str(inputs.get("seed", case.name)),
    )


def _parse_rendered_model_answer(model_answer: str) -> dict[str, Any] | None:
    text = str(model_answer or "").strip()
    if not text:
        return None
    steps: list[dict[str, Any]] = []
    pattern = re.compile(
        r"Issue\s+\d+:\s*(?P<issue>.*?)\n"
        r"Rule:\s*(?P<rule>.*?)\n"
        r"Application:\s*(?P<application>.*?)\n"
        r"Conclusion:\s*(?P<conclusion>.*?)(?:\nCitations:\s*(?P<citations>.*?))?"
        r"(?=\n\nIssue\s+\d+:|\n\nOverall conclusion:|\Z)",
        re.DOTALL,
    )
    for match in pattern.finditer(text):
        citations = [
            {"corpus_id": token.strip()}
            for token in str(match.group("citations") or "").split(",")
            if token.strip()
        ]
        steps.append(
            {
                "issue": match.group("issue").strip(),
                "rule": match.group("rule").strip(),
                "application": match.group("application").strip(),
                "conclusion": match.group("conclusion").strip(),
                "citations": citations,
            }
        )
    if not steps:
        return None
    overall = text.split("Overall conclusion:", 1)[-1].strip()
    return {"steps": steps, "overall_conclusion": overall if overall != text else ""}


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


async def jikai_eval_v1_task(case: EvalCase) -> str:
    from src.config import settings
    from src.services.corpus_service import corpus_service
    from src.services.hypothetical_service import hypothetical_service
    from src.services.llm_service import llm_service
    from src.services.vector_service import vector_service
    from src.services.verification.nli_verifier import nli_verifier

    topics = _topics(case)
    query = str(case.inputs.get("query", " ".join(topics))).strip()
    corpus_pack = str(case.metadata.get("corpus_pack", "sg_tort"))
    jurisdiction = str(case.metadata.get("jurisdiction", "sg"))
    subject = str(case.metadata.get("subject", case.metadata.get("law_domain", "tort")))
    top_k = int(case.inputs.get("top_k", case.expected_output.get("recall_k", 5)))
    corpus = await corpus_service.load_corpus(corpus_pack=corpus_pack)
    documents = [_entry_to_document(entry) for entry in corpus]
    query_terms = topics + ([query] if query and query not in topics else [])
    retrieval_mode = str(
        case.inputs.get(
            "retrieval_mode",
            case.metadata.get(
                "retrieval_mode", getattr(settings, "retrieval_mode", "hybrid")
            ),
        )
    ).lower()
    if retrieval_mode == "bm25":
        retrieved = vector_service._bm25_rank_documents(
            " ".join(query_terms),
            documents,
            n_results=top_k,
        )
    elif retrieval_mode == "dense":
        retrieved = await vector_service.semantic_search(
            query_topics=query_terms,
            corpus_pack=corpus_pack,
            jurisdiction=jurisdiction,
            subject=subject,
            subtopics=list(case.metadata.get("subtopics", []) or []),
            n_results=top_k,
            min_similarity=0.0,
        )
    else:
        retrieval_mode = "hybrid"
        retrieved = await vector_service.hybrid_search(
            query_topics=query_terms,
            corpus_documents=documents,
            corpus_pack=corpus_pack,
            jurisdiction=jurisdiction,
            subject=subject,
            subtopics=list(case.metadata.get("subtopics", []) or []),
            n_results=top_k,
        )
    case.metadata["retrieval_mode"] = retrieval_mode
    case.metadata["retrieved_ids"] = [
        str(result.get("id")) for result in retrieved if result.get("id")
    ]

    async with _HYPO_GENERATOR_LOCK:
        result = await hypothetical_service.generate_hypothetical(
            _build_request_from_case(case)
        )

    validation = dict(getattr(result, "validation_results", {}) or {})
    model_answer = _parse_rendered_model_answer(getattr(result, "model_answer", ""))
    case.metadata["model_answer"] = model_answer
    if validation.get("citation"):
        case.metadata["citation_report"] = validation["citation"]

    if validation.get("faithfulness"):
        case.metadata["faithfulness_report"] = validation["faithfulness"]
    else:
        contexts = [
            {"corpus_id": str(row.get("id", "")), "text": str(row.get("text", ""))}
            for row in retrieved
        ]
        claims = await nli_verifier.extract_claims(result.hypothetical, llm_service)
        case.metadata["faithfulness_report"] = nli_verifier.verify(
            claims, contexts
        ).model_dump()

    return str(result.hypothetical)


TASKS: dict[str, Task] = {
    "sg_tort_hypothetical": sg_tort_hypothetical_task,
    "sg_citation_retrieval": sg_citation_retrieval_task,
    "sg_statute_interpretation_mcq": sg_statute_interpretation_mcq_task,
    "sg_factual_reasoning": sg_factual_reasoning_task,
    "jikai_eval_v1": jikai_eval_v1_task,
}

__all__ = [
    "TASKS",
    "Task",
    "sg_tort_hypothetical_task",
    "sg_citation_retrieval_task",
    "sg_statute_interpretation_mcq_task",
    "sg_factual_reasoning_task",
    "jikai_eval_v1_task",
]
