"""Anthropic LLM provider using anthropic SDK."""

import time
from typing import Any, AsyncIterator, Dict, List, Optional

import structlog

from .base import (
    LLMProvider,
    LLMRequest,
    LLMResponse,
    LLMServiceError,
    retry_on_failure,
)

logger = structlog.get_logger(__name__)

ANTHROPIC_MODELS = [
    "claude-sonnet-4-5-20250929",
    "claude-haiku-4-5-20251001",
    "claude-opus-4-6",
]


class AnthropicProvider(LLMProvider):
    """Anthropic Claude provider implementation."""

    def __init__(
        self,
        api_key: str = None,
        default_model: str = "claude-sonnet-4-5-20250929",
        timeout: int = 120,
    ):
        self.default_model = default_model
        self.timeout = timeout
        try:
            import anthropic

            self._api_key = api_key
            self.client = anthropic.AsyncAnthropic(api_key=api_key, timeout=timeout)
        except ImportError:
            raise LLMServiceError("anthropic package not installed")

    @retry_on_failure(max_attempts=3, delay=2.0, backoff=2.0)
    async def generate(self, request: LLMRequest) -> LLMResponse:
        start_time = time.time()
        model = request.model or self.default_model
        try:
            kwargs: Dict[str, Any] = {
                "model": model,
                "max_tokens": request.max_tokens,
                "temperature": request.temperature,
                "messages": [{"role": "user", "content": request.prompt}],
            }
            if request.system_prompt:
                kwargs["system"] = request.system_prompt
            message = await self.client.messages.create(**kwargs)
            response_time = time.time() - start_time
            content = message.content[0].text if message.content else ""
            return LLMResponse(
                content=content,
                model=message.model,
                usage={
                    "prompt_tokens": message.usage.input_tokens,
                    "completion_tokens": message.usage.output_tokens,
                    "total_tokens": message.usage.input_tokens
                    + message.usage.output_tokens,
                },
                finish_reason=message.stop_reason or "stop",
                response_time=response_time,
                metadata={"id": message.id},
            )
        except Exception as e:
            logger.error("Anthropic generation failed", error=str(e))
            raise LLMServiceError(f"Anthropic error: {e}")

    async def list_models(self) -> List[str]:
        return ANTHROPIC_MODELS

    async def health_check(self) -> Dict[str, Any]:
        try:
            await self.client.messages.create(
                model=self.default_model,
                max_tokens=1,
                messages=[{"role": "user", "content": "ping"}],
            )
            return {"healthy": True, "provider": "anthropic"}
        except Exception as e:
            return {"healthy": False, "provider": "anthropic", "error": str(e)}

    async def stream_generate(self, request: LLMRequest) -> AsyncIterator[str]:
        model = request.model or self.default_model
        kwargs: Dict[str, Any] = {
            "model": model,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "messages": [{"role": "user", "content": request.prompt}],
        }
        if request.system_prompt:
            kwargs["system"] = request.system_prompt
        async with self.client.messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                yield text

    async def close(self):
        await self.client.close()
