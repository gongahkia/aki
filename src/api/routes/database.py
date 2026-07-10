"""Database and history endpoints."""

from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()


class StudentAttemptRequest(BaseModel):
    generation_id: Optional[int] = None
    topics: List[str] = Field(min_length=1, max_length=10)
    self_rating: Optional[int] = Field(default=None, ge=1, le=5)
    rubric_misses: List[str] = Field(default_factory=list)
    notes: Optional[str] = None
    elapsed_seconds: Optional[int] = Field(default=None, ge=0)
    attempted_at: Optional[str] = None


@router.get("/history")
async def get_history(limit: int = 500):
    from ...services import database_service

    records = await database_service.get_history_records(limit=limit)
    return {"records": records, "count": len(records)}


@router.get("/generation/{generation_id}")
async def get_generation(generation_id: int):
    from ...services import database_service

    record = await database_service.get_generation_by_id(generation_id)
    if record is None:
        return {"error": "not_found"}
    return record


@router.get("/count")
async def get_count():
    from ...services import database_service

    count = await database_service.get_generation_count()
    return {"count": count}


@router.get("/statistics")
async def get_statistics():
    from ...services import database_service

    return await database_service.get_statistics()


@router.get("/reports/{generation_id}")
async def get_reports(generation_id: int):
    from ...services import database_service

    reports = await database_service.get_generation_reports(generation_id)
    return {
        "reports": [
            r.model_dump() if hasattr(r, "model_dump") else r.__dict__ for r in reports
        ]
    }


@router.post("/progress/attempts")
async def save_student_attempt(request: StudentAttemptRequest):
    from ...services import StudentAttempt, database_service

    try:
        attempt_id = await database_service.save_student_attempt(
            StudentAttempt(
                generation_id=request.generation_id,
                topics=request.topics,
                self_rating=request.self_rating,
                rubric_misses=request.rubric_misses,
                notes=request.notes,
                elapsed_seconds=request.elapsed_seconds,
                attempted_at=request.attempted_at,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"attempt_id": attempt_id}


@router.get("/progress/attempts")
async def get_student_attempts(limit: int = 100):
    from ...services import database_service

    attempts = await database_service.get_student_attempts(limit=limit)
    return {"attempts": attempts, "count": len(attempts)}


@router.get("/progress/weak-topics")
async def get_weak_topics(limit: int = 10):
    from ...services import database_service

    topics = await database_service.get_weak_topics(limit=limit)
    return {"weak_topics": topics, "count": len(topics)}


@router.get("/progress/spaced-queue")
async def get_spaced_repetition_queue(limit: int = 10):
    from ...services import database_service

    queue = await database_service.get_spaced_repetition_queue(limit=limit)
    return {"spaced_repetition_queue": queue, "count": len(queue)}


@router.get("/progress/study-plan")
async def export_study_plan(days: int = 7):
    from ...services import database_service

    return await database_service.export_study_plan(days=days)


@router.get("/progress/summary")
async def get_progress_summary(limit: int = 10):
    from ...services import database_service

    return await database_service.get_progress_summary(limit=limit)
