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


def _profile_payload(profile: Any) -> Dict[str, Any]:
    return {
        "key": profile.key,
        "display_name": profile.display_name,
        "corpus_pack": profile.corpus_pack_key,
        "syllabus_topics": list(profile.syllabus_topics),
        "allowed_authority_ids": list(profile.allowed_authority_ids),
        "difficulty_profile": dict(profile.difficulty_profile or {}),
        "exam_style": dict(profile.exam_style or {}),
        "data_backed": profile.data_backed,
        "data_sources": list(profile.data_sources),
        "notes": profile.notes,
    }


def _pack_source_ids(manifest_path: str) -> List[str]:
    import json
    from pathlib import Path

    path = Path(manifest_path)
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[3] / path
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    sources = payload.get("sources", [])
    if not isinstance(sources, list):
        return []
    return [
        str(source["registry_source_id"])
        for source in sources
        if isinstance(source, dict) and source.get("registry_source_id")
    ]


@router.get("/topics")
async def list_topics(
    corpus_pack: str = "sg_tort",
    jurisdiction: str = "sg",
    subject: str = "tort",
):
    from ...services import corpus_service

    topics = await corpus_service.extract_all_topics(
        corpus_pack=corpus_pack,
        jurisdiction=jurisdiction,
        subject=subject,
    )
    return {
        "topics": topics,
        "corpus_pack": corpus_pack,
        "jurisdiction": jurisdiction,
        "subject": subject,
    }


@router.get("/packs")
async def list_packs():
    from ...domain import list_domain_packs

    return {
        "packs": [
            {
                "key": pack.key,
                "display_name": pack.display_name,
                "jurisdiction": pack.jurisdiction_key,
                "subject": pack.subject_key,
                "topic_count": len(pack.topic_keys),
                "topics": list(pack.topic_keys),
                "manifest_path": pack.manifest_path,
                "corpus_path": pack.corpus_path,
                "record_format": pack.record_format,
                "source_ids": _pack_source_ids(pack.manifest_path),
                "course_profiles": [
                    _profile_payload(profile)
                    for profile in (pack.course_profiles or {}).values()
                ],
            }
            for pack in list_domain_packs()
        ]
    }


@router.get("/profiles")
async def list_profiles(corpus_pack: Optional[str] = None):
    from ...domain import list_course_profiles

    profiles = list_course_profiles(corpus_pack=corpus_pack)
    return {"profiles": [_profile_payload(profile) for profile in profiles]}


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
        entries = [e for e in entries if topic in e.topics]
    entries = entries[:limit]
    return {
        "entries": [
            e.student_view(include_model_answer=include_model_answer) for e in entries
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
