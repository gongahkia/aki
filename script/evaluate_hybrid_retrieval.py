#!/usr/bin/env python3
"""A/B Recall@K check for dense vs hybrid retrieval."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.corpus_service import CorpusService, HypotheticalEntry  # noqa: E402
from src.services.vector_service import VectorService  # noqa: E402


def _document_payload(entries: List[HypotheticalEntry]) -> List[Dict[str, Any]]:
    return [
        {
            "id": entry.id,
            "text": entry.text,
            "topics": entry.topics,
            "corpus_pack_key": entry.corpus_pack_key,
            "jurisdiction": entry.jurisdiction,
            "subject": entry.subject,
            "subtopics": entry.subtopics,
            "metadata": entry.metadata,
        }
        for entry in entries
        if entry.id
    ]


def _query_topics(entry: HypotheticalEntry, max_topics: int) -> List[str]:
    topics = list(entry.topics)
    if max_topics > 0:
        topics = topics[:max_topics]
    return topics or ["negligence"]


async def _dense_ids(
    service: VectorService,
    entry: HypotheticalEntry,
    *,
    k: int,
    max_topics: int,
) -> List[str]:
    if service._fallback_mode:  # local eval transparency, not production branch
        return []
    results = await service.semantic_search(
        query_topics=_query_topics(entry, max_topics),
        corpus_pack=entry.corpus_pack_key,
        jurisdiction=entry.jurisdiction,
        subject=entry.subject,
        subtopics=entry.subtopics,
        n_results=k,
        min_similarity=0.0,
    )
    return [str(result["id"]) for result in results]


async def _hybrid_ids(
    service: VectorService,
    entry: HypotheticalEntry,
    *,
    documents: List[Dict[str, Any]],
    k: int,
    max_topics: int,
) -> List[str]:
    results = await service.hybrid_search(
        query_topics=_query_topics(entry, max_topics),
        corpus_documents=documents,
        corpus_pack=entry.corpus_pack_key,
        jurisdiction=entry.jurisdiction,
        subject=entry.subject,
        subtopics=entry.subtopics,
        n_results=k,
        min_similarity=0.0,
    )
    return [str(result["id"]) for result in results]


async def evaluate(args: argparse.Namespace) -> Dict[str, Any]:
    corpus_service = CorpusService()
    vector_service = VectorService()
    entries = await corpus_service.load_corpus(corpus_pack=args.corpus_pack)
    entries = [entry for entry in entries if entry.id and entry.topics]
    if args.limit > 0:
        entries = entries[: args.limit]
    documents = _document_payload(entries)
    if not entries:
        raise SystemExit("no corpus entries to evaluate")

    indexed_count = 0
    if not args.skip_index:
        indexed_count = await vector_service.index_hypotheticals(documents)

    dense_hits = 0
    hybrid_hits = 0
    misses = []
    for entry in entries:
        target_id = str(entry.id)
        dense = await _dense_ids(
            vector_service,
            entry,
            k=args.k,
            max_topics=args.max_topics,
        )
        hybrid = await _hybrid_ids(
            vector_service,
            entry,
            documents=documents,
            k=args.k,
            max_topics=args.max_topics,
        )
        dense_hit = target_id in dense
        hybrid_hit = target_id in hybrid
        dense_hits += int(dense_hit)
        hybrid_hits += int(hybrid_hit)
        if dense_hit and not hybrid_hit:
            misses.append({"id": target_id, "topics": entry.topics})

    total = len(entries)
    dense_recall = dense_hits / total
    hybrid_recall = hybrid_hits / total
    return {
        "corpus_pack": args.corpus_pack,
        "k": args.k,
        "cases": total,
        "indexed_count": indexed_count,
        "dense_branch_available": not vector_service._fallback_mode,
        "dense_recall_at_k": dense_recall,
        "hybrid_recall_at_k": hybrid_recall,
        "hybrid_gte_dense": hybrid_recall >= dense_recall,
        "dense_hits": dense_hits,
        "hybrid_hits": hybrid_hits,
        "hybrid_misses_where_dense_hit": misses,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus-pack", default="sg_tort")
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--max-topics", type=int, default=0)
    parser.add_argument("--skip-index", action="store_true")
    parser.add_argument("--output")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = asyncio.run(evaluate(args))
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        "Recall@{k}: dense={dense:.3f} hybrid={hybrid:.3f} "
        "hybrid_gte_dense={gte} cases={cases}".format(
            k=result["k"],
            dense=result["dense_recall_at_k"],
            hybrid=result["hybrid_recall_at_k"],
            gte=result["hybrid_gte_dense"],
            cases=result["cases"],
        )
    )


if __name__ == "__main__":
    main()
