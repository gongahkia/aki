"""Google Gemini LLM provider using google-generativeai SDK."""

import time
from typing import Any, AsyncIterator, Dict, List, Optional

import structlog
from pydantic import BaseModel, ValidationError

from .base import (
    LLMProvider,
    LLMRequest,
    LLMResponse,
    LLMServiceError,
    retry_on_failure,
)

logger = structlog.get_logger(__name__)

GEMINI_MODELS = [
    "gemini-2.0-flash",
    "gemini-2.5-pro",
]


class GoogleGeminiProvider(LLMProvider):
    """Google Gemini provider implementation."""

    supports_json_schema = True

    def __init__(
        self,
        api_key: Optional[str] = None,
        default_model: str = "gemini-2.0-flash",
        timeout: int = 120,
    ):
        self.default_model = default_model
        self.timeout = timeout
        try:
            import google.generativeai as genai

            self._genai = genai
            self._api_key = api_key
            if api_key:
                genai.configure(api_key=api_key)
        except ImportError:
            raise LLMServiceError("google-generativeai package not installed")

    @retry_on_failure(max_attempts=3, delay=2.0, backoff=2.0)
    async def generate(self, request: LLMRequest) -> LLMResponse:
        import asyncio

        start_time = time.time()
        model_name = request.model or self.default_model
        try:
            model = self._genai.GenerativeModel(
                model_name=model_name,
                system_instruction=request.system_prompt or None,
            )
            config = self._genai.types.GenerationConfig(
                temperature=request.temperature,
                max_output_tokens=request.max_tokens,
            )
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    model.generate_content, request.prompt, generation_config=config
                ),
                timeout=30,
            )
            response_time = time.time() - start_time
            # handle safety filter blocks
            if hasattr(response, "prompt_feedback") and response.prompt_feedback:
                block_reason = getattr(response.prompt_feedback, "block_reason", None)
                if block_reason:
                    raise LLMServiceError(f"Gemini content filtered: {block_reason}")
            content = ""
            try:
                content = response.text or ""
            except (ValueError, AttributeError):
                logger.warning("Gemini response.text is None/unavailable")
                return LLMResponse(
                    content="",
                    model=model_name,
                    usage={},
                    finish_reason="error",
                    response_time=response_time,
                )
            usage = {}
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                um = response.usage_metadata
                usage = {
                    "prompt_tokens": getattr(um, "prompt_token_count", 0),
                    "completion_tokens": getattr(um, "candidates_token_count", 0),
                    "total_tokens": getattr(um, "total_token_count", 0),
                }
            return LLMResponse(
                content=content,
                model=model_name,
                usage=usage,
                finish_reason="stop",
                response_time=response_time,
            )
        except asyncio.TimeoutError:
            raise LLMServiceError("Google Gemini timed out after 30s")
        except LLMServiceError:
            raise
        except Exception as e:
            logger.error("Google Gemini generation failed", error=str(e))
            raise LLMServiceError(f"Google Gemini error: {e}")

    async def list_models(self) -> List[str]:
        return GEMINI_MODELS

    @retry_on_failure(max_attempts=2, delay=1.0, backoff=2.0)
    async def generate_structured(
        self,
        schema: type[BaseModel],
        prompt: str,
        *,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        model: Optional[str] = None,
        **kwargs: Any,
    ) -> BaseModel:
        model_name = model or self.default_model
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        try:
            import instructor

            client_kwargs: Dict[str, Any] = {"async_client": True}
            api_key = getattr(self, "_api_key", None)
            if api_key:
                client_kwargs["api_key"] = api_key
            client = instructor.from_provider(f"google/{model_name}", **client_kwargs)
            result = await client.create(
                response_model=schema,
                messages=messages,
                max_retries=2,
                generation_config={
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
            )
            return schema.model_validate(result)
        except ValidationError:
            raise
        except ImportError as e:
            raise LLMServiceError("instructor package not installed") from e
        except Exception as e:
            raise LLMServiceError(f"Google Gemini structured error: {e}") from e

    async def health_check(self) -> Dict[str, Any]:
        try:
            import asyncio

            model = self._genai.GenerativeModel(self.default_model)
            await asyncio.to_thread(
                model.generate_content,
                "ping",
                generation_config=self._genai.types.GenerationConfig(
                    max_output_tokens=1
                ),
            )
            return {"healthy": True, "provider": "google"}
        except Exception as e:
            return {"healthy": False, "provider": "google", "error": str(e)}

    async def stream_generate(self, request: LLMRequest) -> AsyncIterator[str]:
        import asyncio

        model_name = request.model or self.default_model
        model = self._genai.GenerativeModel(
            model_name=model_name,
            system_instruction=request.system_prompt or None,
        )
        config = self._genai.types.GenerationConfig(
            temperature=request.temperature,
            max_output_tokens=request.max_tokens,
        )
        response = await asyncio.to_thread(
            model.generate_content,
            request.prompt,
            generation_config=config,
            stream=True,
        )
        for chunk in response:
            if chunk.text:
                yield chunk.text
