"""Corpus management endpoints."""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter()


class CorpusQueryRequest(BaseModel):
    topics: List[str]
    corpus_pack: str = "sg_tort"
    jurisdiction: str = "sg"
    subject: str = "tort"
    subtopics: List[str] = Field(default_factory=list)
    sample_size: int = Field(default=5, ge=1, le=50)
    exclude_ids: List[str] = Field(default_factory=list)
    min_topic_overlap: int = Field(default=1, ge=1)
    include_model_answer: bool = False


class AddEntryRequest(BaseModel):
    text: str
    topics: List[str]
    question_prompt: Optional[str] = None
    fact_pattern: Optional[str] = None
    issues_expected: List[str] = Field(default_factory=list)
    model_answer: Optional[str] = None
    marking_rubric: Any = None
    difficulty: Optional[str] = None
    time_limit_minutes: Optional[int] = None
    jurisdiction_notes: Optional[str] = None
    answer_visibility: str = "hidden"
    source_exam_context: Dict[str, Any] = Field(default_factory=dict)
    corpus_pack: str = "sg_tort"
    jurisdiction: str = "sg"
    subject: str = "tort"
    subtopics: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


@router.get("/topics")
async def list_topics():
    from ...services import corpus_service

    topics = await corpus_service.extract_all_topics()
    return {"topics": topics}


@router.get("/entries")
async def list_entries(
    topic: Optional[str] = None,
    limit: int = 500,
    corpus_pack: str = "sg_tort",
    jurisdiction: str = "sg",
    subject: str = "tort",
    include_model_answer: bool = False,
):
    from ...services import corpus_service

    entries = await corpus_service.load_corpus(corpus_pack=corpus_pack)
    entries = [
        e
        for e in entries
        if e.corpus_pack_key == corpus_pack
        and e.jurisdiction == jurisdiction
        and e.subject == subject
    ]
    if topic:
        entries = [
            e
            for e in entries
            if topic in (e.topics if hasattr(e, "topics") else e.get("topics", []))
        ]
    entries = entries[:limit]
    return {
        "entries": [
            (
                e.student_view(include_model_answer=include_model_answer)
                if hasattr(e, "student_view")
                else e
            )
            for e in entries
        ],
        "count": len(entries),
    }


@router.post("/query")
async def query_corpus(req: CorpusQueryRequest):
    from ...services import corpus_service
    from ...services.corpus_service import CorpusQuery

    query = CorpusQuery(
        topics=req.topics,
        corpus_pack=req.corpus_pack,
        jurisdiction=req.jurisdiction,
        subject=req.subject,
        subtopics=req.subtopics,
        sample_size=req.sample_size,
        exclude_ids=req.exclude_ids,
        min_topic_overlap=req.min_topic_overlap,
    )
    results = await corpus_service.query_relevant_hypotheticals(query)
    return {
        "entries": [
            (
                r.student_view(include_model_answer=req.include_model_answer)
                if hasattr(r, "student_view")
                else r
            )
            for r in results
        ],
        "count": len(results),
    }


@router.post("/add")
async def add_entry(req: AddEntryRequest):
    from ...services import corpus_service
    from ...services.corpus_service import HypotheticalEntry

    entry = HypotheticalEntry(
        text=req.text,
        topics=req.topics,
        question_prompt=req.question_prompt,
        fact_pattern=req.fact_pattern,
        issues_expected=req.issues_expected,
        model_answer=req.model_answer,
        marking_rubric=req.marking_rubric,
        difficulty=req.difficulty,
        time_limit_minutes=req.time_limit_minutes,
        jurisdiction_notes=req.jurisdiction_notes,
        answer_visibility=req.answer_visibility,
        source_exam_context=req.source_exam_context,
        corpus_pack_key=req.corpus_pack,
        jurisdiction=req.jurisdiction,
        subject=req.subject,
        subtopics=req.subtopics,
        metadata=req.metadata,
    )
    entry_id = await corpus_service.add_hypothetical(entry)
    return {"id": entry_id}


@router.get("/health")
async def corpus_health():
    from ...services import corpus_service

    return await corpus_service.health_check()
