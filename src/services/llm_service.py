"""
LLM Service for handling interactions with various language models.
Supports multiple providers including Ollama, OpenAI, and others.
"""

import asyncio
import json
from typing import Dict, List, Optional, Any, Union
from abc import ABC, abstractmethod
import httpx
import structlog
from pydantic import BaseModel, Field

from ..config import settings

logger = structlog.get_logger(__name__)


class LLMRequest(BaseModel):
    """Request model for LLM calls."""
    prompt: str
    system_prompt: Optional[str] = None
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2048, gt=0)
    model: Optional[str] = None
    stream: bool = False


class LLMResponse(BaseModel):
    """Response model for LLM calls."""
    content: str
    model: str
    usage: Dict[str, int] = Field(default_factory=dict)
    finish_reason: str = "stop"
    response_time: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    @abstractmethod
    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate a response from the LLM."""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the provider is healthy."""
        pass


class OllamaProvider(LLMProvider):
    """Ollama LLM provider implementation."""
    
    def __init__(self, base_url: str = None, timeout: int = 30):
        self.base_url = base_url or settings.llm.ollama_host
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)
    
    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate response using Ollama."""
        try:
            import time
            start_time = time.time()
            
            # Prepare the request payload
            payload = {
                "model": request.model or settings.llm.model_name,
                "prompt": request.prompt,
                "stream": request.stream,
                "options": {
                    "temperature": request.temperature,
                    "num_predict": request.max_tokens,
                }
            }
            
            if request.system_prompt:
                payload["system"] = request.system_prompt
            
            logger.info("Sending request to Ollama", model=payload["model"], prompt_length=len(request.prompt))
            
            response = await self.client.post(
                f"{self.base_url}/api/generate",
                json=payload
            )
            response.raise_for_status()
            
            # Parse the response
            response_data = response.json()
            response_time = time.time() - start_time
            
            return LLMResponse(
                content=response_data.get("response", ""),
                model=response_data.get("model", payload["model"]),
                usage={
                    "prompt_tokens": response_data.get("prompt_eval_count", 0),
                    "completion_tokens": response_data.get("eval_count", 0),
                    "total_tokens": response_data.get("prompt_eval_count", 0) + response_data.get("eval_count", 0)
                },
                finish_reason=response_data.get("done", True) and "stop" or "incomplete",
                response_time=response_time,
                metadata={
                    "load_duration": response_data.get("load_duration", 0),
                    "prompt_eval_duration": response_data.get("prompt_eval_duration", 0),
                    "eval_duration": response_data.get("eval_duration", 0),
                    "total_duration": response_data.get("total_duration", 0),
                }
            )
            
        except httpx.HTTPError as e:
            logger.error("HTTP error in Ollama request", error=str(e))
            raise LLMServiceError(f"HTTP error: {e}")
        except Exception as e:
            logger.error("Unexpected error in Ollama request", error=str(e))
            raise LLMServiceError(f"Unexpected error: {e}")
    
    async def health_check(self) -> bool:
        """Check if Ollama is healthy."""
        try:
            response = await self.client.get(f"{self.base_url}/api/tags")
            return response.status_code == 200
        except Exception as e:
            logger.error("Ollama health check failed", error=str(e))
            return False
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


class OpenAIProvider(LLMProvider):
    """OpenAI LLM provider implementation."""
    
    def __init__(self, api_key: str, base_url: str = "https://api.openai.com/v1", timeout: int = 30):
        self.api_key = api_key
        self.base_url = base_url
        self.timeout = timeout
        self.client = httpx.AsyncClient(
            timeout=timeout,
            headers={"Authorization": f"Bearer {api_key}"}
        )
    
    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate response using OpenAI API."""
        try:
            import time
            start_time = time.time()
            
            messages = []
            if request.system_prompt:
                messages.append({"role": "system", "content": request.system_prompt})
            messages.append({"role": "user", "content": request.prompt})
            
            payload = {
                "model": request.model or "gpt-3.5-turbo",
                "messages": messages,
                "temperature": request.temperature,
                "max_tokens": request.max_tokens,
                "stream": request.stream
            }
            
            logger.info("Sending request to OpenAI", model=payload["model"], prompt_length=len(request.prompt))
            
            response = await self.client.post(
                f"{self.base_url}/chat/completions",
                json=payload
            )
            response.raise_for_status()
            
            response_data = response.json()
            response_time = time.time() - start_time
            
            choice = response_data["choices"][0]
            usage = response_data.get("usage", {})
            
            return LLMResponse(
                content=choice["message"]["content"],
                model=response_data["model"],
                usage={
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                    "total_tokens": usage.get("total_tokens", 0)
                },
                finish_reason=choice.get("finish_reason", "stop"),
                response_time=response_time,
                metadata=response_data
            )
            
        except httpx.HTTPError as e:
            logger.error("HTTP error in OpenAI request", error=str(e))
            raise LLMServiceError(f"HTTP error: {e}")
        except Exception as e:
            logger.error("Unexpected error in OpenAI request", error=str(e))
            raise LLMServiceError(f"Unexpected error: {e}")
    
    async def health_check(self) -> bool:
        """Check if OpenAI API is healthy."""
        try:
            response = await self.client.get(f"{self.base_url}/models")
            return response.status_code == 200
        except Exception as e:
            logger.error("OpenAI health check failed", error=str(e))
            return False
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


class LLMServiceError(Exception):
    """Custom exception for LLM service errors."""
    pass


class LLMService:
    """Main LLM service that manages different providers."""
    
    def __init__(self):
        self._providers: Dict[str, LLMProvider] = {}
        self._default_provider = None
        self._initialize_providers()
    
    def _initialize_providers(self):
        """Initialize available LLM providers."""
        # Initialize Ollama provider
        if settings.llm.provider.lower() == "ollama":
            ollama_provider = OllamaProvider()
            self._providers["ollama"] = ollama_provider
            self._default_provider = "ollama"
        
        # Initialize OpenAI provider if API key is available
        openai_key = getattr(settings, 'openai_api_key', None)
        if openai_key:
            openai_provider = OpenAIProvider(openai_key)
            self._providers["openai"] = openai_provider
            if not self._default_provider:
                self._default_provider = "openai"
        
        logger.info("LLM providers initialized", providers=list(self._providers.keys()), default=self._default_provider)
    
    async def generate(self, request: LLMRequest, provider: str = None) -> LLMResponse:
        """Generate a response using the specified or default provider."""
        provider_name = provider or self._default_provider
        
        if not provider_name or provider_name not in self._providers:
            raise LLMServiceError(f"Provider '{provider_name}' not available")
        
        provider_instance = self._providers[provider_name]
        
        try:
            response = await provider_instance.generate(request)
            logger.info("LLM generation completed", 
                       provider=provider_name, 
                       model=response.model,
                       response_time=response.response_time,
                       tokens=response.usage.get("total_tokens", 0))
            return response
        except Exception as e:
            logger.error("LLM generation failed", provider=provider_name, error=str(e))
            raise
    
    async def health_check(self, provider: str = None) -> Dict[str, bool]:
        """Check health of all or specific provider."""
        if provider:
            if provider not in self._providers:
                return {provider: False}
            return {provider: await self._providers[provider].health_check()}
        
        # Check all providers
        health_status = {}
        for name, provider_instance in self._providers.items():
            health_status[name] = await provider_instance.health_check()
        
        return health_status
    
    async def list_models(self, provider: str = None) -> Dict[str, List[str]]:
        """List available models for providers."""
        # This would need to be implemented per provider
        # For now, return default models
        models = {
            "ollama": ["llama2:7b", "llama2:13b", "codellama:7b"],
            "openai": ["gpt-3.5-turbo", "gpt-4", "gpt-4-turbo"]
        }
        
        if provider:
            return {provider: models.get(provider, [])}
        return models
    
    async def close(self):
        """Close all provider connections."""
        for provider in self._providers.values():
            if hasattr(provider, 'close'):
                await provider.close()
        logger.info("All LLM providers closed")


# Global LLM service instance
llm_service = LLMService()
