"""Typed history models and validators for TUI history records."""

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator


class HistoryConfig(BaseModel):
    """Validated generation config payload stored in history records."""

    model_config = ConfigDict(extra="forbid")

    topic: str = ""
    topics: List[str] = Field(default_factory=list)
    provider: Optional[str] = None
    model: Optional[str] = None
    complexity: Union[int, str] = "intermediate"
    parties: int = Field(default=3, ge=2, le=5)
    method: str = "pure_llm"


class TUIHistoryRecord(BaseModel):
    """Validated TUI history record shape."""

    model_config = ConfigDict(extra="forbid")

    generation_id: Optional[int] = Field(default=None, ge=1)
    timestamp: str
    config: HistoryConfig
    hypothetical: str = ""
    analysis: str = ""
    model_answer: str = ""
    validation_score: float = Field(default=0.0, ge=0.0, le=10.0)
    parent_generation_id: Optional[int] = Field(default=None, ge=1)
    retry_reason: Optional[str] = None
    retry_attempt: int = Field(default=0, ge=0)
    regenerated_from: Optional[int] = Field(default=None, ge=1)
    report_id: Optional[int] = Field(default=None, ge=1)
    report_issue_types: List[str] = Field(default_factory=list)
    report_comment: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_payload(cls, value: Any) -> Dict[str, Any]:
        if not isinstance(value, dict):
            raise TypeError("history record must be a dict")

        payload = dict(value)
        if "validation_score" not in payload and "score" in payload:
            payload["validation_score"] = payload.pop("score")
        payload.setdefault("timestamp", datetime.utcnow().isoformat())
        payload.setdefault("analysis", "")
        payload.setdefault("model_answer", "")
        payload.setdefault("validation_score", 0.0)
        payload.setdefault("hypothetical", "")

        config = payload.get("config")
        if not isinstance(config, dict):
            config = {}
        config = dict(config)
        raw_topics = config.get("topics", [])
        if not isinstance(raw_topics, list):
            raw_topics = [str(raw_topics)] if raw_topics else []
        config["topics"] = [str(topic) for topic in raw_topics if str(topic).strip()]
        if not config.get("topic") and config["topics"]:
            config["topic"] = config["topics"][0]
        config.setdefault("topic", "")
        config.setdefault("parties", 3)
        config.setdefault("method", "pure_llm")
        payload["config"] = config

        return payload


def validate_history_records(records: List[Any]) -> Tuple[List[Dict[str, Any]], int]:
    """Validate and normalize a list of history records.

    Returns (validated_records, dropped_count).
    """

    validated: List[Dict[str, Any]] = []
    dropped = 0
    for record in records:
        if not isinstance(record, dict):
            dropped += 1
            continue
        try:
            model = TUIHistoryRecord.model_validate(record)
        except ValidationError:
            dropped += 1
            continue
        validated.append(model.model_dump())
    return validated, dropped
