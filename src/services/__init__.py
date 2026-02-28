"""Services package for Jikai application."""

from .database_service import (
    DatabaseService,
    GenerationFeedback,
    GenerationReport,
    database_service,
)
from .hypothetical_service import (
    GenerationRequest,
    GenerationResponse,
    HypotheticalService,
    ValidationResult,
    hypothetical_service,
)
from .llm_service import LLMRequest, LLMResponse, LLMService, llm_service
from .validation_service import ValidationService, validation_service

try:
    from .corpus_service import (
        CorpusQuery,
        CorpusService,
        HypotheticalEntry,
        corpus_service,
    )
    from .vector_service import VectorService, vector_service

    _HAS_VECTOR = True
except Exception:
    _HAS_VECTOR = False


__all__ = [
    "normalize_topic",
    "LLMService",
    "LLMRequest",
    "LLMResponse",
    "llm_service",
    "DatabaseService",
    "GenerationReport",
    "GenerationFeedback",
    "database_service",
    "HypotheticalService",
    "hypothetical_service",
    "GenerationRequest",
    "GenerationResponse",
    "ValidationResult",
    "ValidationService",
    "validation_service",
]

if _HAS_VECTOR:
    __all__ += [
        "CorpusService",
        "HypotheticalEntry",
        "CorpusQuery",
        "corpus_service",
        "VectorService",
        "vector_service",
    ]


def normalize_topic(topic: str) -> str:
    """Normalize topic key: lowercase, underscores to spaces, stripped."""
    return topic.lower().replace("_", " ").strip()
