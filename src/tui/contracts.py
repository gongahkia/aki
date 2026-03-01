"""Typed service contracts for TUI dependency injection."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol


class GenerationService(Protocol):
    """Generation dependency required by Rich/Textual generation flows."""

    async def generate_hypothetical(self, request: Any) -> Any: ...

    def clear_response_cache(self) -> None: ...


class HistoryService(Protocol):
    """Persistence dependency required by history/reporting flows."""

    async def get_history_records(self, limit: int = 500) -> List[Dict[str, Any]]: ...

    async def save_generation(
        self,
        *,
        request_data: Dict[str, Any],
        response_data: Dict[str, Any],
        correlation_id: Optional[str] = None,
    ) -> int: ...


class ProviderService(Protocol):
    """Provider dependency required by provider/settings flows."""

    async def health_check(self, provider: Optional[str] = None) -> Dict[str, Any]: ...

    async def list_models(
        self, provider: Optional[str] = None
    ) -> Dict[str, List[str]]: ...

    def select_provider(self, name: str) -> None: ...

    def select_model(self, name: str) -> None: ...


class CorpusServiceContract(Protocol):
    """Corpus dependency required by generation warmup/lookup flows."""

    async def extract_all_topics(self) -> List[str]: ...

    async def query_relevant_hypotheticals(self, query: Any) -> List[Any]: ...


class WorkflowService(Protocol):
    """Workflow orchestration dependency for generate/report/regenerate flows."""

    async def generate_generation(
        self,
        request: Any,
        *,
        correlation_id: Optional[str] = None,
    ) -> Any: ...

    async def save_generation_report(
        self,
        *,
        generation_id: int,
        issue_types: List[str],
        comment: Optional[str],
        is_locked: bool = True,
    ) -> int: ...

    async def regenerate_generation(
        self,
        *,
        generation_id: int,
        correlation_id: Optional[str] = None,
        fallback_request: Optional[Dict[str, Any]] = None,
    ) -> Any: ...

    async def list_generation_reports(self, generation_id: int) -> Any: ...
