"""
LLM Service using provider registry for multi-provider support.
"""
import asyncio
import structlog
from typing import Dict, List, Optional, Any
from .llm_providers import registry, LLMRequest, LLMResponse, LLMServiceError

from ..config import settings

logger = structlog.get_logger(__name__)

GENERATION_TIMEOUT = 120  # seconds
HEALTH_CHECK_TIMEOUT = 30  # seconds


class LLMService:
    """Main LLM service that manages providers via registry."""

    def __init__(self):
        self._default_provider: Optional[str] = None
        self._default_model: Optional[str] = None
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

    async def generate(self, request: LLMRequest, provider: str = None, model: str = None) -> LLMResponse:
        """Generate using specified or default provider+model."""
        provider_name = provider or self._default_provider
        if not provider_name or provider_name not in registry.list_instances():
            raise LLMServiceError(f"Provider '{provider_name}' not available")
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
            logger.info("LLM generation completed",
                       provider=provider_name, model=response.model,
                       response_time=response.response_time,
                       tokens=response.usage.get("total_tokens", 0))
            return response
        except asyncio.TimeoutError:
            raise LLMServiceError(f"Generation timed out after {GENERATION_TIMEOUT}s on provider '{provider_name}'")
        except Exception as e:
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
