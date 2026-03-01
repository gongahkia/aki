"""TTL cache for provider health and model snapshots."""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Tuple


class ProviderHealthCache:
    """Caches provider health snapshots and model lists with TTL."""

    def __init__(self, ttl_seconds: float = 20.0) -> None:
        self._ttl_seconds = max(1.0, float(ttl_seconds))
        self._snapshot: Dict[str, Any] = {}
        self._provider_model_cache: Dict[str, List[str]] = {}

    def invalidate(self) -> None:
        self._snapshot.clear()
        self._provider_model_cache.clear()

    def get_snapshot(
        self,
        fetch_snapshot: Callable[[], Tuple[Dict[str, Any], Dict[str, List[str]]]],
        *,
        force_refresh: bool = False,
    ) -> Tuple[Dict[str, Any], Dict[str, List[str]]]:
        now = time.monotonic()
        if not force_refresh and self._snapshot:
            if float(self._snapshot.get("expires_at", 0.0)) > now:
                health = self._snapshot.get("health", {})
                models = self._snapshot.get("models", {})
                if isinstance(health, dict) and isinstance(models, dict):
                    return health, models

        try:
            health, models = fetch_snapshot()
        except Exception:
            self.invalidate()
            raise
        normalized_models: Dict[str, List[str]] = {}
        for provider_name, model_list in models.items():
            if not isinstance(model_list, list):
                normalized_models[provider_name] = []
                continue
            cleaned = sorted(
                {
                    model.strip()
                    for model in model_list
                    if isinstance(model, str) and model.strip()
                }
            )
            normalized_models[provider_name] = cleaned
            self._provider_model_cache[provider_name] = cleaned

        self._snapshot = {
            "expires_at": now + self._ttl_seconds,
            "health": health,
            "models": normalized_models,
        }
        return health, normalized_models

    def get_provider_models(
        self,
        provider: str,
        fetch_models: Callable[[str], List[str]],
        *,
        force_refresh: bool = False,
    ) -> List[str]:
        provider_name = (provider or "").strip().lower()
        if not provider_name:
            return []

        if not force_refresh and provider_name in self._provider_model_cache:
            return self._provider_model_cache[provider_name]

        if not force_refresh and self._snapshot:
            now = time.monotonic()
            if float(self._snapshot.get("expires_at", 0.0)) > now:
                cached_models = self._snapshot.get("models", {}).get(provider_name)
                if isinstance(cached_models, list):
                    self._provider_model_cache[provider_name] = cached_models
                    return cached_models

        try:
            models = fetch_models(provider_name)
        except Exception:
            self.invalidate()
            raise
        unique_models = sorted({m for m in models if isinstance(m, str) and m.strip()})
        self._provider_model_cache[provider_name] = unique_models
        return unique_models
