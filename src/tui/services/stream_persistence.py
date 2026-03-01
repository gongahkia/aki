"""Shared stream-generation persistence utilities for TUI runtimes."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

_LAST_STREAM_GENERATION_ID: Optional[int] = None
_LAST_STREAM_DATABASE_SERVICE: Any = None


def resolve_stream_persist_database_service(generation_id: int) -> Any:
    if _LAST_STREAM_GENERATION_ID == generation_id:
        return _LAST_STREAM_DATABASE_SERVICE
    return None


async def persist_stream_generation(
    *,
    topic: str,
    provider: str,
    model: Optional[str],
    complexity: int,
    parties: int,
    method: str,
    temperature: float,
    red_herrings: bool,
    hypothetical: str,
    validation_results: Dict[str, Any],
    correlation_id: Optional[str] = None,
    include_analysis: bool = False,
    partial_snapshot: bool = False,
    cancellation_metadata: Optional[Dict[str, Any]] = None,
) -> int:
    """Persist a stream-generated result for report/regenerate workflows."""
    from ...services.database_service import database_service
    from ...services.workflow_facade import workflow_facade

    request_data: Dict[str, Any] = {
        "topics": [topic],
        "law_domain": "tort",
        "number_parties": parties,
        "complexity_level": str(complexity),
        "sample_size": 3,
        "user_preferences": {
            "temperature": temperature,
            "red_herrings": red_herrings,
        },
        "method": method,
        "provider": provider,
        "model": model,
        "correlation_id": correlation_id,
        "include_analysis": include_analysis,
    }
    if cancellation_metadata:
        request_data["user_preferences"]["cancellation_metadata"] = dict(
            cancellation_metadata
        )

    response_data: Dict[str, Any] = {
        "hypothetical": hypothetical,
        "analysis": "",
        "metadata": {
            "topics": [topic],
            "law_domain": "tort",
            "number_parties": parties,
            "complexity_level": str(complexity),
            "partial_snapshot": partial_snapshot,
            "cancellation_metadata": dict(cancellation_metadata or {}),
            "generation_timestamp": datetime.utcnow().isoformat(),
        },
        "generation_time": 0.0,
        "validation_results": validation_results,
    }

    generation_id = await database_service.save_generation(
        request_data=request_data,
        response_data=response_data,
        correlation_id=correlation_id,
    )
    global _LAST_STREAM_GENERATION_ID, _LAST_STREAM_DATABASE_SERVICE
    _LAST_STREAM_GENERATION_ID = int(generation_id)
    _LAST_STREAM_DATABASE_SERVICE = database_service
    if hasattr(database_service, "_db_path"):
        setattr(workflow_facade, "_database_service", database_service)
    return int(generation_id)
