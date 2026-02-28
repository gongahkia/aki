"""Abstract LLM provider interface and provider registry."""

import asyncio
import random
from abc import ABC, abstractmethod
from functools import wraps
from typing import Any, AsyncIterator, Dict, List, Optional

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)


def retry_on_failure(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    jitter_ratio: float = 0.2,
):
    """Decorator for retrying async functions with exponential backoff."""

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_delay = delay
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_attempts:
                        logger.error(
                            f"{func.__name__} failed after {max_attempts} attempts",
                            error=str(e),
                        )
                        raise
                    sleep_for = current_delay
                    if jitter_ratio > 0:
                        spread = current_delay * jitter_ratio
                        sleep_for = max(
                            0.0,
                            current_delay + random.uniform(-spread, spread),
                        )
                    logger.warning(
                        f"{func.__name__} attempt {attempt}/{max_attempts} failed, retrying in {sleep_for:.2f}s",
                        error=str(e),
                    )
                    await asyncio.sleep(sleep_for)
                    current_delay *= backoff
            return None

        return wrapper

    return decorator


class LLMRequest(BaseModel):
    """Request model for LLM calls."""

    prompt: str
    system_prompt: Optional[str] = None
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2048, gt=0)
    model: Optional[str] = None
    stream: bool = False
    correlation_id: Optional[str] = None
    timeout_seconds: Optional[int] = Field(default=None, ge=1)


class LLMResponse(BaseModel):
    """Response model for LLM calls."""

    content: str
    model: str
    usage: Dict[str, int] = Field(default_factory=dict)
    finish_reason: str = "stop"
    response_time: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class LLMServiceError(Exception):
    """Custom exception for LLM service errors."""


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate a response from the LLM."""

    @abstractmethod
    async def list_models(self) -> List[str]:
        """List available models for this provider."""

    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Check provider health. Returns dict with 'healthy' bool and details."""

    async def stream_generate(self, request: LLMRequest) -> AsyncIterator[str]:
        """Stream generate tokens. Default: yield full response at once."""
        response = await self.generate(request)
        yield response.content

    async def close(self):
        """Cleanup resources."""


class ProviderRegistry:
    """Registry for LLM provider classes. Supports register/get/list."""

    def __init__(self):
        self._providers: Dict[str, type] = {}
        self._instances: Dict[str, LLMProvider] = {}

    def register(self, name: str, provider_class: type):
        """Register a provider class by name."""
        self._providers[name] = provider_class

    def get(self, name: str, **kwargs) -> LLMProvider:
        """Get or create a provider instance by name."""
        if name not in self._providers:
            raise LLMServiceError(f"Provider '{name}' not registered")
        if name not in self._instances:
            self._instances[name] = self._providers[name](**kwargs)
        return self._instances[name]

    def list_providers(self) -> List[str]:
        """List registered provider names."""
        return list(self._providers.keys())

    def list_instances(self) -> List[str]:
        """List instantiated provider names."""
        return list(self._instances.keys())

    def set_instance(self, name: str, instance: LLMProvider):
        """Set a pre-built provider instance."""
        self._instances[name] = instance

    async def close_all(self):
        """Close all active provider instances."""
        for instance in self._instances.values():
            await instance.close()
        self._instances.clear()
