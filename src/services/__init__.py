"""Services package for Jikai application."""

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

from .database_service import DatabaseService, database_service
from .hypothetical_service import (
    GenerationRequest,
    GenerationResponse,
    HypotheticalService,
    ValidationResult,
    hypothetical_service,
)
from .llm_service import LLMRequest, LLMResponse, LLMService, llm_service
from .validation_service import ValidationService, validation_service

__all__ = [
    "LLMService",
    "LLMRequest",
    "LLMResponse",
    "llm_service",
    "DatabaseService",
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
