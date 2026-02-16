"""OpenAI LLM provider conforming to base interface."""

import time
from typing import Any, AsyncIterator, Dict, List
import httpx
import structlog
from .base import (
    LLMProvider,
    LLMRequest,
    LLMResponse,
    LLMServiceError,
    retry_on_failure,
)

logger = structlog.get_logger(__name__)

OPENAI_MODELS = ["gpt-4o", "gpt-4o-mini", "o1", "o3-mini"]


class OpenAIProvider(LLMProvider):
    """OpenAI provider with dynamic model listing."""

    def __init__(
        self,
        api_key: str = None,
        base_url: str = "https://api.openai.com/v1",
        default_model: str = "gpt-4o",
        timeout: int = 120,
    ):
        self.api_key = api_key or ""
        self.base_url = base_url
        self.default_model = default_model
        self.timeout = timeout
        self.client = httpx.AsyncClient(
            timeout=timeout,
            headers={"Authorization": f"Bearer {self.api_key}"},
        )

    @retry_on_failure(max_attempts=3, delay=2.0, backoff=2.0)
    async def generate(self, request: LLMRequest) -> LLMResponse:
        start_time = time.time()
        model = request.model or self.default_model
        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.prompt})
        payload = {
            "model": model,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }
        try:
            resp = await self.client.post(
                f"{self.base_url}/chat/completions", json=payload
            )
            resp.raise_for_status()
            data = resp.json()
            choice = data["choices"][0]
            usage = data.get("usage", {})
            return LLMResponse(
                content=choice["message"]["content"],
                model=data["model"],
                usage={
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                    "total_tokens": usage.get("total_tokens", 0),
                },
                finish_reason=choice.get("finish_reason", "stop"),
                response_time=time.time() - start_time,
                metadata={"id": data.get("id", "")},
            )
        except httpx.HTTPError as e:
            raise LLMServiceError(f"OpenAI HTTP error: {e}")
        except Exception as e:
            raise LLMServiceError(f"OpenAI error: {e}")

    async def list_models(self) -> List[str]:
        """Dynamically list models from OpenAI API."""
        try:
            resp = await self.client.get(f"{self.base_url}/models")
            resp.raise_for_status()
            data = resp.json()
            return [m["id"] for m in data.get("data", [])]
        except Exception:
            return OPENAI_MODELS

    async def health_check(self) -> Dict[str, Any]:
        try:
            resp = await self.client.get(f"{self.base_url}/models")
            return {"healthy": resp.status_code == 200, "provider": "openai"}
        except Exception as e:
            return {"healthy": False, "provider": "openai", "error": str(e)}

    async def stream_generate(self, request: LLMRequest) -> AsyncIterator[str]:
        model = request.model or self.default_model
        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.prompt})
        payload = {
            "model": model,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "stream": True,
        }
        import json as json_mod

        async with self.client.stream(
            "POST", f"{self.base_url}/chat/completions", json=payload
        ) as resp:
            async for line in resp.aiter_lines():
                if line.startswith("data: ") and line != "data: [DONE]":
                    data = json_mod.loads(line[6:])
                    delta = data.get("choices", [{}])[0].get("delta", {})
                    if content := delta.get("content", ""):
                        yield content

    async def close(self):
        await self.client.aclose()
