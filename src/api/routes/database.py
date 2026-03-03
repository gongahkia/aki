"""Database and history endpoints."""

from fastapi import APIRouter

router = APIRouter()


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
