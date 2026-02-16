"""
LLM Service using provider registry for multi-provider support.
"""
import asyncio
import time
import structlog
from typing import Dict, List, Optional, Any
from .llm_providers import registry, LLMRequest, LLMResponse, LLMServiceError

from ..config import settings

logger = structlog.get_logger(__name__)

GENERATION_TIMEOUT = 120
HEALTH_CHECK_TIMEOUT = 30
CIRCUIT_BREAKER_THRESHOLD = 3  # consecutive failures before marking unhealthy
CIRCUIT_BREAKER_COOLDOWN = 60

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
            registry.set_instance("ollama", OllamaProvider(base_url=ollama_host, default_model=model_name))
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
                registry.set_instance("anthropic", AnthropicProvider(api_key=anthropic_key))
                if not self._default_provider:
                    self._default_provider = "anthropic"
            except Exception as e:
                logger.warning("Failed to init Anthropic provider", error=str(e))

        # google
        google_key = getattr(settings, "google_api_key", None)
        if google_key:
            try:
                from .llm_providers.google_provider import GoogleGeminiProvider
                registry.set_instance("google", GoogleGeminiProvider(api_key=google_key))
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

        logger.info("LLM providers initialized", active=registry.list_instances(), default=self._default_provider)

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

    def _record_failure(self, name: str):
        """Record a failure; trip circuit breaker after threshold."""
        self._failure_counts[name] = self._failure_counts.get(name, 0) + 1
        if self._failure_counts[name] >= CIRCUIT_BREAKER_THRESHOLD:
            self._unhealthy_until[name] = time.time() + CIRCUIT_BREAKER_COOLDOWN
            logger.warning("Circuit breaker tripped", provider=name, cooldown=CIRCUIT_BREAKER_COOLDOWN)

    def _record_success(self, name: str):
        self._failure_counts[name] = 0

    def _track_cost(self, model: str, usage: Dict[str, int]):
        """Estimate and accumulate token costs."""
        costs = TOKEN_COSTS.get(model, {"input": 0, "output": 0})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        cost = (input_tokens / 1000 * costs["input"]) + (output_tokens / 1000 * costs["output"])
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
        for name in registry.list_instances():
            if name != exclude and self._is_provider_healthy(name):
                return name
        return None

    async def generate(self, request: LLMRequest, provider: str = None, model: str = None) -> LLMResponse:
        """Generate using specified or default provider+model. Auto-fallback on circuit break."""
        provider_name = provider or self._default_provider
        if not provider_name or provider_name not in registry.list_instances():
            raise LLMServiceError(f"Provider '{provider_name}' not available")
        # circuit breaker check
        if not self._is_provider_healthy(provider_name):
            fallback = self._get_fallback_provider(provider_name)
            if fallback:
                logger.warning("Provider unhealthy, falling back", unhealthy=provider_name, fallback=fallback)
                provider_name = fallback
            else:
                raise LLMServiceError(f"Provider '{provider_name}' is circuit-broken and no fallback available")
        if model:
            request = request.model_copy(update={"model": model})
        elif self._default_model and not request.model:
            request = request.model_copy(update={"model": self._default_model})
        provider_instance = registry.get(provider_name)
        try:
            response = await asyncio.wait_for(
                provider_instance.generate(request),
                timeout=GENERATION_TIMEOUT,
            )
            self._record_success(provider_name)
            cost = self._track_cost(response.model, response.usage)
            logger.info("LLM generation completed",
                       provider=provider_name, model=response.model,
                       response_time=response.response_time,
                       tokens=response.usage.get("total_tokens", 0),
                       cost_usd=round(cost, 6))
            return response
        except asyncio.TimeoutError:
            self._record_failure(provider_name)
            raise LLMServiceError(f"Generation timed out after {GENERATION_TIMEOUT}s on provider '{provider_name}'")
        except Exception as e:
            self._record_failure(provider_name)
            logger.error("LLM generation failed", provider=provider_name, error=str(e))
            raise

    async def health_check(self, provider: str = None) -> Dict[str, Any]:
        """Check health of all or specific provider."""
        if provider:
            if provider not in registry.list_instances():
                return {provider: {"healthy": False, "error": "not initialized"}}
            try:
                return {provider: await asyncio.wait_for(registry.get(provider).health_check(), timeout=HEALTH_CHECK_TIMEOUT)}
            except asyncio.TimeoutError:
                return {provider: {"healthy": False, "error": f"health check timed out after {HEALTH_CHECK_TIMEOUT}s"}}
        results = {}
        for name in registry.list_instances():
            try:
                results[name] = await asyncio.wait_for(registry.get(name).health_check(), timeout=HEALTH_CHECK_TIMEOUT)
            except asyncio.TimeoutError:
                results[name] = {"healthy": False, "error": f"health check timed out after {HEALTH_CHECK_TIMEOUT}s"}
        return results

    async def list_models(self, provider: str = None) -> Dict[str, List[str]]:
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
