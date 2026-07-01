"""
LLM Service using provider registry for multi-provider support.
"""

import asyncio
import random
import time
from typing import Any, Dict, List, Optional

import httpx
import structlog

from ..config import settings
from .llm_providers import LLMRequest, LLMResponse, LLMServiceError, registry

logger = structlog.get_logger(__name__)

GENERATION_TIMEOUT = 120
MIN_GENERATION_TIMEOUT = 10
MAX_GENERATION_TIMEOUT = 300
HEALTH_CHECK_TIMEOUT = 30
CIRCUIT_BREAKER_THRESHOLD = 3  # consecutive failures before marking unhealthy
CIRCUIT_BREAKER_COOLDOWN = settings.llm_providers.circuit_breaker_cooldown
CIRCUIT_BREAKER_JITTER_RATIO = 0.2
PROVIDER_FALLBACK_ORDER = ("ollama", "local", "openai", "google", "anthropic")
CIRCUIT_BREAKER_FAILURE_KINDS = {
    "timeout",
    "provider_5xx",
    "rate_limit",
    "provider_down",
    "unknown",
}

# cost per 1K tokens (USD) - configurable
TOKEN_COSTS = {
    "claude-sonnet-4-5-20250929": {"input": 0.003, "output": 0.015},
    "claude-haiku-4-5-20251001": {"input": 0.001, "output": 0.005},
    "claude-opus-4-6": {"input": 0.015, "output": 0.075},
    "gpt-4o": {"input": 0.005, "output": 0.015},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "o1": {"input": 0.015, "output": 0.06},
    "o3-mini": {"input": 0.0011, "output": 0.0044},
    "gemini-2.0-flash": {"input": 0.0001, "output": 0.0004},
    "gemini-2.5-pro": {"input": 0.00125, "output": 0.005},
}

PROVIDER_CAPABILITIES: Dict[str, Dict[str, Any]] = {
    "ollama": {
        "supports_stream": True,
        "supports_system_prompt": True,
        "max_tokens": 8192,
    },
    "openai": {
        "supports_stream": True,
        "supports_system_prompt": True,
        "max_tokens": 16384,
    },
    "anthropic": {
        "supports_stream": True,
        "supports_system_prompt": True,
        "max_tokens": 8192,
    },
    "google": {
        "supports_stream": True,
        "supports_system_prompt": True,
        "max_tokens": 8192,
    },
    "local": {
        "supports_stream": True,
        "supports_system_prompt": True,
        "max_tokens": 4096,
    },
}

DEFAULT_PROVIDER_CAPABILITIES: Dict[str, Any] = {
    "supports_stream": True,
    "supports_system_prompt": True,
    "max_tokens": 2048,
}


class LLMService:
    """Main LLM service that manages providers via registry."""

    def __init__(self):
        self._default_provider: Optional[str] = None
        self._default_model: Optional[str] = None
        self._failure_counts: Dict[str, int] = {}
        self._unhealthy_until: Dict[str, float] = {}
        self._session_cost: float = 0.0
        self._session_tokens: Dict[str, int] = {"input": 0, "output": 0}
        self._initialize_providers()

    def _initialize_providers(self):
        """Initialize configured providers."""
        # ollama (always available, local)
        try:
            ollama_host = getattr(settings.llm, "ollama_host", "http://localhost:11434")
            model_name = getattr(settings.llm, "model_name", "llama2:7b")
            from .llm_providers.ollama_provider import OllamaProvider

            registry.set_instance(
                "ollama", OllamaProvider(base_url=ollama_host, default_model=model_name)
            )
            if not self._default_provider:
                self._default_provider = "ollama"
                self._default_model = model_name
        except Exception as e:
            logger.warning("Failed to init Ollama provider", error=str(e))

        # openai
        openai_key = getattr(settings, "openai_api_key", None)
        if openai_key:
            try:
                from .llm_providers.openai_provider import OpenAIProvider

                registry.set_instance("openai", OpenAIProvider(api_key=openai_key))
                if not self._default_provider:
                    self._default_provider = "openai"
            except Exception as e:
                logger.warning("Failed to init OpenAI provider", error=str(e))

        # anthropic
        anthropic_key = getattr(settings, "anthropic_api_key", None)
        if anthropic_key:
            try:
                from .llm_providers.anthropic_provider import AnthropicProvider

                registry.set_instance(
                    "anthropic", AnthropicProvider(api_key=anthropic_key)
                )
                if not self._default_provider:
                    self._default_provider = "anthropic"
            except Exception as e:
                logger.warning("Failed to init Anthropic provider", error=str(e))

        # google
        google_key = getattr(settings, "google_api_key", None)
        if google_key:
            try:
                from .llm_providers.google_provider import GoogleGeminiProvider

                registry.set_instance(
                    "google", GoogleGeminiProvider(api_key=google_key)
                )
                if not self._default_provider:
                    self._default_provider = "google"
            except Exception as e:
                logger.warning("Failed to init Google provider", error=str(e))

        # local llm
        local_host = getattr(settings, "local_llm_host", None)
        if local_host:
            try:
                from .llm_providers.local_provider import LocalLLMProvider

                registry.set_instance("local", LocalLLMProvider(base_url=local_host))
            except Exception as e:
                logger.warning("Failed to init Local LLM provider", error=str(e))

        configured_providers = [
            getattr(settings.llm, "provider", None),
            getattr(settings.llm_providers, "default_provider", None),
        ]
        active_providers = registry.list_instances()
        for configured in configured_providers:
            provider = str(configured or "").strip().lower()
            if provider in active_providers:
                self._default_provider = provider
                break
        configured_model = str(
            getattr(settings.llm, "model_name", None)
            or getattr(settings.llm_providers, "default_model", "")
        ).strip()
        if configured_model:
            self._default_model = configured_model

        logger.info(
            "LLM providers initialized",
            active=registry.list_instances(),
            default=self._default_provider,
        )

    def select_provider(self, name: str):
        """Set default provider by name."""
        if name not in registry.list_instances():
            raise LLMServiceError(f"Provider '{name}' not available")
        self._default_provider = name

    def select_model(self, name: str):
        """Set default model."""
        self._default_model = name

    def _is_provider_healthy(self, name: str) -> bool:
        """Check if provider is not circuit-broken."""
        if name in self._unhealthy_until:
            if time.time() < self._unhealthy_until[name]:
                return False
            del self._unhealthy_until[name]
            self._failure_counts[name] = 0
        return True

    @staticmethod
    def _fallback_rank(name: str) -> int:
        try:
            return PROVIDER_FALLBACK_ORDER.index(name)
        except ValueError:
            return len(PROVIDER_FALLBACK_ORDER)

    @staticmethod
    def _classify_failure(error: BaseException) -> str:
        if isinstance(error, (asyncio.TimeoutError, TimeoutError)):
            return "timeout"
        if isinstance(error, httpx.HTTPStatusError):
            status = error.response.status_code
            if status == 429:
                return "rate_limit"
            if 500 <= status < 600:
                return "provider_5xx"
            if status in {401, 403, 404}:
                return "permanent"
        if isinstance(error, (httpx.ConnectError, httpx.NetworkError, ConnectionError)):
            return "provider_down"

        message = str(error).lower()
        if any(
            token in message for token in ("rate limit", "too many requests", "429")
        ):
            return "rate_limit"
        if any(token in message for token in ("timed out", "timeout")):
            return "timeout"
        if any(
            token in message
            for token in (
                " 500",
                "500.",
                " 502",
                "502.",
                " 503",
                "503.",
                " 504",
                "504.",
                "5xx",
                "server error",
                "status error 5",
            )
        ):
            return "provider_5xx"
        if any(
            token in message
            for token in (
                "connection",
                "refused",
                "unreachable",
                "all connection attempts failed",
                "network",
                "provider down",
                "transport error",
            )
        ):
            return "provider_down"
        if any(
            token in message
            for token in (
                "api key",
                "apikey",
                "authentication",
                "unauthorized",
                "forbidden",
                "401",
                "403",
            )
        ):
            return "permanent"
        if "model" in message and any(
            token in message
            for token in ("not found", "not available", "does not exist")
        ):
            return "permanent"
        return "unknown"

    def _should_trip_circuit(self, error: BaseException) -> bool:
        return self._classify_failure(error) in CIRCUIT_BREAKER_FAILURE_KINDS

    @staticmethod
    def _cooldown_with_jitter() -> float:
        cooldown = float(CIRCUIT_BREAKER_COOLDOWN)
        if CIRCUIT_BREAKER_JITTER_RATIO <= 0 or cooldown <= 0:
            return cooldown
        spread = cooldown * CIRCUIT_BREAKER_JITTER_RATIO
        return max(1.0, cooldown + random.uniform(-spread, spread))

    def _record_failure(self, name: str, *, failure_kind: str = "unknown"):
        """Record a failure; trip circuit breaker after threshold."""
        if len(self._failure_counts) > 1000:
            oldest = next(iter(self._failure_counts))
            del self._failure_counts[oldest]
        self._failure_counts[name] = self._failure_counts.get(name, 0) + 1
        if self._failure_counts[name] >= CIRCUIT_BREAKER_THRESHOLD:
            cooldown = self._cooldown_with_jitter()
            self._unhealthy_until[name] = time.time() + cooldown
            logger.warning(
                "Circuit breaker tripped",
                provider=name,
                failure_kind=failure_kind,
                cooldown=round(cooldown, 2),
            )

    def _record_success(self, name: str):
        self._failure_counts[name] = 0

    def get_provider_capabilities(self, provider: str) -> Dict[str, Any]:
        """Get capability profile for a provider."""
        caps = PROVIDER_CAPABILITIES.get(provider, {})
        merged = dict(DEFAULT_PROVIDER_CAPABILITIES)
        merged.update(caps)
        return merged

    def _validate_generation_config(self, provider: str, request: LLMRequest):
        """Validate request against provider capability map before provider call."""
        caps = self.get_provider_capabilities(provider)

        if request.stream and not bool(caps.get("supports_stream", False)):
            raise LLMServiceError(
                f"Provider '{provider}' does not support streaming generation"
            )

        if request.system_prompt and not bool(
            caps.get("supports_system_prompt", False)
        ):
            raise LLMServiceError(
                f"Provider '{provider}' does not support system prompts"
            )

        max_tokens = caps.get("max_tokens")
        if isinstance(max_tokens, int) and request.max_tokens > max_tokens:
            raise LLMServiceError(
                f"max_tokens={request.max_tokens} exceeds provider '{provider}' limit ({max_tokens})"
            )

    @staticmethod
    def _extract_correlation_id(request: LLMRequest) -> Optional[str]:
        raw = (request.correlation_id or "").strip()
        return raw or None

    @staticmethod
    def _resolve_request_timeout(request: LLMRequest) -> int:
        if request.timeout_seconds is None:
            return GENERATION_TIMEOUT
        try:
            requested = int(request.timeout_seconds)
        except (TypeError, ValueError):
            return GENERATION_TIMEOUT
        return max(MIN_GENERATION_TIMEOUT, min(MAX_GENERATION_TIMEOUT, requested))

    def _track_cost(self, model: str, usage: Dict[str, int]):
        """Estimate and accumulate token costs."""
        costs = TOKEN_COSTS.get(model, {"input": 0, "output": 0})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        cost = (input_tokens / 1000 * costs["input"]) + (
            output_tokens / 1000 * costs["output"]
        )
        self._session_cost += cost
        self._session_tokens["input"] += input_tokens
        self._session_tokens["output"] += output_tokens
        return cost

    def get_session_cost(self) -> Dict[str, Any]:
        """Get accumulated session cost info."""
        return {
            "total_cost_usd": round(self._session_cost, 6),
            "total_input_tokens": self._session_tokens["input"],
            "total_output_tokens": self._session_tokens["output"],
        }

    def _get_fallback_provider(self, exclude: str) -> Optional[str]:
        """Get next available healthy provider."""
        candidates = [
            name
            for name in registry.list_instances()
            if name != exclude and self._is_provider_healthy(name)
        ]
        if not candidates:
            return None
        return sorted(candidates, key=lambda name: (self._fallback_rank(name), name))[0]

    async def generate(
        self,
        request: LLMRequest,
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ) -> LLMResponse:
        """Generate using specified or default provider+model. Auto-fallback on circuit break."""
        correlation_id = self._extract_correlation_id(request)
        request_timeout = self._resolve_request_timeout(request)
        provider_name = provider or self._default_provider
        if not provider_name or provider_name not in registry.list_instances():
            raise LLMServiceError(f"Provider '{provider_name}' not available")
        # circuit breaker check
        if not self._is_provider_healthy(provider_name):
            fallback = self._get_fallback_provider(provider_name)
            if fallback:
                logger.warning(
                    "Provider unhealthy, falling back",
                    unhealthy=provider_name,
                    fallback=fallback,
                    correlation_id=correlation_id,
                )
                provider_name = fallback
            else:
                raise LLMServiceError(
                    f"Provider '{provider_name}' is circuit-broken and no fallback available"
                )
        if model:
            request = request.model_copy(update={"model": model})
        elif self._default_model and not request.model:
            request = request.model_copy(update={"model": self._default_model})
        self._validate_generation_config(provider_name, request)
        provider_instance = registry.get(provider_name)
        try:
            response = await asyncio.wait_for(
                provider_instance.generate(request),
                timeout=request_timeout,
            )
            self._record_success(provider_name)
            cost = self._track_cost(response.model, response.usage)
            logger.info(
                "LLM generation completed",
                provider=provider_name,
                model=response.model,
                response_time=response.response_time,
                tokens=response.usage.get("total_tokens", 0),
                cost_usd=round(cost, 6),
                correlation_id=correlation_id,
            )
            return response
        except asyncio.TimeoutError as e:
            self._record_failure(provider_name, failure_kind="timeout")
            logger.warning(
                "LLM generation timed out",
                provider=provider_name,
                timeout_seconds=request_timeout,
                correlation_id=correlation_id,
            )
            raise LLMServiceError(
                f"Generation timed out after {request_timeout}s on provider '{provider_name}'"
            ) from e
        except Exception as e:
            failure_kind = self._classify_failure(e)
            if self._should_trip_circuit(e):
                self._record_failure(provider_name, failure_kind=failure_kind)
            else:
                logger.info(
                    "LLM generation failed without circuit breaker trip",
                    provider=provider_name,
                    failure_kind=failure_kind,
                    correlation_id=correlation_id,
                )
            logger.error(
                "LLM generation failed",
                provider=provider_name,
                failure_kind=failure_kind,
                error=str(e),
                correlation_id=correlation_id,
            )
            raise

    async def stream_generate(
        self,
        request: LLMRequest,
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ):
        """Stream tokens from provider. Yields str chunks."""
        correlation_id = self._extract_correlation_id(request)
        request_timeout = self._resolve_request_timeout(request)
        provider_name = provider or self._default_provider
        if not provider_name or provider_name not in registry.list_instances():
            raise LLMServiceError(f"Provider '{provider_name}' not available")
        if not self._is_provider_healthy(provider_name):
            fallback = self._get_fallback_provider(provider_name)
            if fallback:
                provider_name = fallback
            else:
                raise LLMServiceError(
                    f"Provider '{provider_name}' is circuit-broken and no fallback available"
                )
        if model:
            request = request.model_copy(update={"model": model, "stream": True})
        else:
            request = request.model_copy(update={"stream": True})
        self._validate_generation_config(provider_name, request)
        provider_instance = registry.get(provider_name)
        try:
            async with asyncio.timeout(request_timeout):
                async for chunk in provider_instance.stream_generate(request):
                    yield chunk
            self._record_success(provider_name)
            logger.info(
                "LLM stream completed",
                provider=provider_name,
                model=request.model,
                correlation_id=correlation_id,
            )
        except TimeoutError as e:
            self._record_failure(provider_name, failure_kind="timeout")
            logger.warning(
                "LLM stream timed out",
                provider=provider_name,
                timeout_seconds=request_timeout,
                correlation_id=correlation_id,
            )
            raise LLMServiceError(
                f"Stream timed out after {request_timeout}s on provider '{provider_name}'"
            ) from e
        except Exception as e:
            failure_kind = self._classify_failure(e)
            if self._should_trip_circuit(e):
                self._record_failure(provider_name, failure_kind=failure_kind)
            else:
                logger.info(
                    "LLM stream failed without circuit breaker trip",
                    provider=provider_name,
                    failure_kind=failure_kind,
                    correlation_id=correlation_id,
                )
            logger.error(
                "LLM stream failed",
                provider=provider_name,
                failure_kind=failure_kind,
                error=str(e),
                correlation_id=correlation_id,
            )
            raise LLMServiceError(f"Stream failed on '{provider_name}': {e}") from e

    async def health_check(self, provider: Optional[str] = None) -> Dict[str, Any]:
        """Check health of all or specific provider."""
        if provider:
            if provider not in registry.list_instances():
                return {provider: {"healthy": False, "error": "not initialized"}}
            try:
                return {
                    provider: await asyncio.wait_for(
                        registry.get(provider).health_check(),
                        timeout=HEALTH_CHECK_TIMEOUT,
                    )
                }
            except asyncio.TimeoutError:
                return {
                    provider: {
                        "healthy": False,
                        "error": f"health check timed out after {HEALTH_CHECK_TIMEOUT}s",
                    }
                }
        results = {}
        for name in registry.list_instances():
            try:
                results[name] = await asyncio.wait_for(
                    registry.get(name).health_check(), timeout=HEALTH_CHECK_TIMEOUT
                )
            except asyncio.TimeoutError:
                results[name] = {
                    "healthy": False,
                    "error": f"health check timed out after {HEALTH_CHECK_TIMEOUT}s",
                }
        return results

    async def list_models(self, provider: Optional[str] = None) -> Dict[str, List[str]]:
        """List models per provider."""
        if provider:
            if provider not in registry.list_instances():
                return {provider: []}
            return {provider: await registry.get(provider).list_models()}
        models = {}
        for name in registry.list_instances():
            models[name] = await registry.get(name).list_models()
        return models

    async def close(self):
        await registry.close_all()
        logger.info("All LLM providers closed")


# global instance
llm_service = LLMService()
