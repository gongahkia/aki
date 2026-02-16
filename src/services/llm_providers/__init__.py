"""LLM provider package with auto-discovery and registry singleton."""
from .base import LLMProvider, LLMRequest, LLMResponse, LLMServiceError, ProviderRegistry

registry = ProviderRegistry()

def _auto_register():
    """Auto-discover and register all provider classes."""
    from .ollama_provider import OllamaProvider
    from .openai_provider import OpenAIProvider
    from .anthropic_provider import AnthropicProvider
    from .google_provider import GoogleGeminiProvider
    from .local_provider import LocalLLMProvider
    registry.register("ollama", OllamaProvider)
    registry.register("openai", OpenAIProvider)
    registry.register("anthropic", AnthropicProvider)
    registry.register("google", GoogleGeminiProvider)
    registry.register("local", LocalLLMProvider)

_auto_register()

__all__ = [
    "LLMProvider", "LLMRequest", "LLMResponse", "LLMServiceError",
    "ProviderRegistry", "registry",
]
