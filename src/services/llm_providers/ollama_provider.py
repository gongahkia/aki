"""Ollama LLM provider conforming to base interface."""

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


class OllamaProvider(LLMProvider):
    """Ollama LLM provider with dynamic model listing."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        default_model: str = "llama2:7b",
        timeout: int = 120,
    ):
        self.base_url = base_url
        self.default_model = default_model
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)

    @retry_on_failure(max_attempts=3, delay=2.0, backoff=2.0)
    async def generate(self, request: LLMRequest) -> LLMResponse:
        start_time = time.time()
        model = request.model or self.default_model
        payload = {
            "model": model,
            "prompt": request.prompt,
            "stream": False,
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_tokens,
            },
        }
        if request.system_prompt:
            payload["system"] = request.system_prompt
        try:
            resp = await self.client.post(f"{self.base_url}/api/generate", json=payload)
            resp.raise_for_status()
            data = resp.json()
            return LLMResponse(
                content=data.get("response", ""),
                model=data.get("model", model),
                usage={
                    "prompt_tokens": data.get("prompt_eval_count", 0),
                    "completion_tokens": data.get("eval_count", 0),
                    "total_tokens": data.get("prompt_eval_count", 0)
                    + data.get("eval_count", 0),
                },
                finish_reason="stop" if data.get("done", True) else "incomplete",
                response_time=time.time() - start_time,
                metadata={
                    "load_duration": data.get("load_duration", 0),
                    "eval_duration": data.get("eval_duration", 0),
                    "total_duration": data.get("total_duration", 0),
                },
            )
        except httpx.HTTPError as e:
            raise LLMServiceError(f"Ollama HTTP error: {e}")
        except Exception as e:
            raise LLMServiceError(f"Ollama error: {e}")

    async def list_models(self) -> List[str]:
        """Dynamically list models via GET /api/tags."""
        try:
            resp = await self.client.get(f"{self.base_url}/api/tags")
            resp.raise_for_status()
            data = resp.json()
            return [m["name"] for m in data.get("models", [])]
        except Exception:
            return [self.default_model]

    async def health_check(self) -> Dict[str, Any]:
        try:
            resp = await self.client.get(f"{self.base_url}/api/tags")
            return {"healthy": resp.status_code == 200, "provider": "ollama"}
        except Exception as e:
            return {"healthy": False, "provider": "ollama", "error": str(e)}

    async def stream_generate(self, request: LLMRequest) -> AsyncIterator[str]:
        model = request.model or self.default_model
        payload = {
            "model": model,
            "prompt": request.prompt,
            "stream": True,
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_tokens,
            },
        }
        if request.system_prompt:
            payload["system"] = request.system_prompt
        import json

        async with self.client.stream(
            "POST", f"{self.base_url}/api/generate", json=payload
        ) as resp:
            async for line in resp.aiter_lines():
                if line:
                    data = json.loads(line)
                    if token := data.get("response", ""):
                        yield token

    async def close(self):
        await self.client.aclose()
