"""Corpus management endpoints."""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter()


class CorpusQueryRequest(BaseModel):
    topics: List[str]
    sample_size: int = Field(default=5, ge=1, le=50)
    exclude_ids: List[str] = Field(default_factory=list)
    min_topic_overlap: int = Field(default=1, ge=1)


class AddEntryRequest(BaseModel):
    text: str
    topics: List[str]
    metadata: Dict[str, Any] = Field(default_factory=dict)


@router.get("/topics")
async def list_topics():
    from ...services import corpus_service

    topics = await corpus_service.extract_all_topics()
    return {"topics": topics}


@router.get("/entries")
async def list_entries(topic: Optional[str] = None, limit: int = 500):
    from ...services import corpus_service

    entries = await corpus_service.load_corpus()
    if topic:
        entries = [
            e
            for e in entries
            if topic in (e.topics if hasattr(e, "topics") else e.get("topics", []))
        ]
    entries = entries[:limit]
    return {
        "entries": [e.model_dump() if hasattr(e, "model_dump") else e for e in entries],
        "count": len(entries),
    }


@router.post("/query")
async def query_corpus(req: CorpusQueryRequest):
    from ...services import corpus_service
    from ...services.corpus_service import CorpusQuery

    query = CorpusQuery(
        topics=req.topics,
        sample_size=req.sample_size,
        exclude_ids=req.exclude_ids,
        min_topic_overlap=req.min_topic_overlap,
    )
    results = await corpus_service.query_relevant_hypotheticals(query)
    return {
        "entries": [r.model_dump() if hasattr(r, "model_dump") else r for r in results],
        "count": len(results),
    }


@router.post("/add")
async def add_entry(req: AddEntryRequest):
    from ...services import corpus_service
    from ...services.corpus_service import HypotheticalEntry

    entry = HypotheticalEntry(text=req.text, topics=req.topics, metadata=req.metadata)
    entry_id = await corpus_service.add_hypothetical(entry)
    return {"id": entry_id}


@router.get("/health")
async def corpus_health():
    from ...services import corpus_service

    return await corpus_service.health_check()
