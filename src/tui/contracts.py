"""Typed service contracts for TUI dependency injection."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol


class GenerationService(Protocol):
    async def generate_hypothetical(self, request: Any) -> Any:
        ...


class HistoryService(Protocol):
    async def get_history_records(self, limit: int = 500) -> List[Dict[str, Any]]:
        ...

    async def save_generation(
        self,
        *,
        request_data: Dict[str, Any],
        response_data: Dict[str, Any],
        correlation_id: Optional[str] = None,
    ) -> int:
        ...


class ProviderService(Protocol):
    async def health_check(self, provider: Optional[str] = None) -> Dict[str, Any]:
        ...

    async def list_models(self, provider: Optional[str] = None) -> Dict[str, List[str]]:
        ...

    def select_provider(self, name: str) -> None:
        ...

    def select_model(self, name: str) -> None:
        ...


class CorpusServiceContract(Protocol):
    async def extract_all_topics(self) -> List[str]:
        ...

    async def query_relevant_hypotheticals(self, query: Any) -> List[Any]:
        ...
