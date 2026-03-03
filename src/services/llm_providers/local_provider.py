"""Local LLM provider supporting llama.cpp server HTTP API."""

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


class LocalLLMProvider(LLMProvider):
    """Local LLM provider via llama.cpp server HTTP API."""

    def __init__(
        self,
        base_url: str = "http://localhost:8080",
        default_model: str = "local",
        timeout: int = 120,
    ):
        self.base_url = base_url
        self.default_model = default_model
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)

    @retry_on_failure(max_attempts=3, delay=2.0, backoff=2.0)
    async def generate(self, request: LLMRequest) -> LLMResponse:
        start_time = time.time()
        payload = {
            "prompt": request.prompt,
            "temperature": request.temperature,
            "n_predict": request.max_tokens,
            "stream": False,
        }
        if request.system_prompt:
            payload["prompt"] = (
                f"### System:\n{request.system_prompt}\n\n### User:\n{request.prompt}\n\n### Assistant:\n"
            )
        try:
            resp = await self.client.post(f"{self.base_url}/completion", json=payload)
            resp.raise_for_status()
            data = resp.json()
            return LLMResponse(
                content=data.get("content", ""),
                model=request.model or self.default_model,
                usage={
                    "prompt_tokens": data.get("tokens_evaluated", 0),
                    "completion_tokens": data.get("tokens_predicted", 0),
                    "total_tokens": data.get("tokens_evaluated", 0)
                    + data.get("tokens_predicted", 0),
                },
                finish_reason=data.get("stop_type", "stop"),
                response_time=time.time() - start_time,
                metadata={"generation_settings": data.get("generation_settings", {})},
            )
        except httpx.HTTPError as e:
            raise LLMServiceError(f"Local LLM HTTP error: {e}")
        except Exception as e:
            raise LLMServiceError(f"Local LLM error: {e}")

    async def list_models(self) -> List[str]:
        """Dynamically query llama.cpp server for loaded model."""
        try:
            resp = await self.client.get(f"{self.base_url}/v1/models")
            resp.raise_for_status()
            data = resp.json()
            return [m["id"] for m in data.get("data", [])]
        except Exception:
            return [self.default_model]

    async def health_check(self) -> Dict[str, Any]:
        try:
            resp = await self.client.get(f"{self.base_url}/health")
            healthy = resp.status_code == 200
            return {"healthy": healthy, "provider": "local"}
        except Exception as e:
            return {"healthy": False, "provider": "local", "error": str(e)}

    async def stream_generate(self, request: LLMRequest) -> AsyncIterator[str]:
        payload = {
            "prompt": request.prompt,
            "temperature": request.temperature,
            "n_predict": request.max_tokens,
            "stream": True,
        }
        if request.system_prompt:
            payload["prompt"] = (
                f"### System:\n{request.system_prompt}\n\n### User:\n{request.prompt}\n\n### Assistant:\n"
            )
        import json

        async with self.client.stream(
            "POST", f"{self.base_url}/completion", json=payload
        ) as resp:
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    data = json.loads(line[6:])
                    if content := data.get("content", ""):
                        yield content

    async def close(self):
        await self.client.aclose()
