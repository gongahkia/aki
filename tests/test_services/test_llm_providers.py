"""Tests for LLM providers: Anthropic, Google Gemini, Local."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.services.llm_providers.base import LLMRequest, LLMResponse, LLMServiceError


@pytest.fixture
def llm_request():
    return LLMRequest(prompt="test prompt", system_prompt="system", temperature=0.7, max_tokens=100)


class TestAnthropicProvider:
    @pytest.mark.asyncio
    async def test_generate_success(self, llm_request):
        with patch("src.services.llm_providers.anthropic_provider.anthropic") as mock_anthropic:
            mock_client = AsyncMock()
            mock_message = MagicMock()
            mock_message.content = [MagicMock(text="response text")]
            mock_message.model = "claude-sonnet-4-5-20250929"
            mock_message.usage.input_tokens = 10
            mock_message.usage.output_tokens = 20
            mock_message.stop_reason = "stop"
            mock_message.id = "msg_123"
            mock_client.messages.create = AsyncMock(return_value=mock_message)
            mock_anthropic.AsyncAnthropic.return_value = mock_client
            from src.services.llm_providers.anthropic_provider import AnthropicProvider
            provider = AnthropicProvider.__new__(AnthropicProvider)
            provider.default_model = "claude-sonnet-4-5-20250929"
            provider.timeout = 120
            provider.client = mock_client
            provider._api_key = "test-key"
            resp = await provider.generate(llm_request)
            assert resp.content == "response text"
            assert resp.model == "claude-sonnet-4-5-20250929"

    @pytest.mark.asyncio
    async def test_list_models(self):
        with patch("src.services.llm_providers.anthropic_provider.anthropic"):
            from src.services.llm_providers.anthropic_provider import AnthropicProvider, ANTHROPIC_MODELS
            provider = AnthropicProvider.__new__(AnthropicProvider)
            models = await provider.list_models()
            assert models == ANTHROPIC_MODELS

    @pytest.mark.asyncio
    async def test_health_check_failure(self):
        with patch("src.services.llm_providers.anthropic_provider.anthropic"):
            from src.services.llm_providers.anthropic_provider import AnthropicProvider
            provider = AnthropicProvider.__new__(AnthropicProvider)
            provider.default_model = "claude-sonnet-4-5-20250929"
            provider.client = AsyncMock()
            provider.client.messages.create = AsyncMock(side_effect=Exception("api error"))
            result = await provider.health_check()
            assert result["healthy"] is False


class TestGoogleGeminiProvider:
    @pytest.mark.asyncio
    async def test_list_models(self):
        from src.services.llm_providers.google_provider import GoogleGeminiProvider, GEMINI_MODELS
        provider = GoogleGeminiProvider.__new__(GoogleGeminiProvider)
        models = await provider.list_models()
        assert models == GEMINI_MODELS

    @pytest.mark.asyncio
    async def test_health_check_failure(self):
        from src.services.llm_providers.google_provider import GoogleGeminiProvider
        provider = GoogleGeminiProvider.__new__(GoogleGeminiProvider)
        provider.default_model = "gemini-2.0-flash"
        provider._genai = MagicMock()
        provider._genai.GenerativeModel.return_value.generate_content.side_effect = Exception("fail")
        result = await provider.health_check()
        assert result["healthy"] is False


class TestLocalLLMProvider:
    @pytest.mark.asyncio
    async def test_generate_success(self, llm_request):
        import httpx
        from src.services.llm_providers.local_provider import LocalLLMProvider
        provider = LocalLLMProvider.__new__(LocalLLMProvider)
        provider.base_url = "http://localhost:8080"
        provider.default_model = "local"
        provider.timeout = 120
        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "content": "generated text",
            "tokens_evaluated": 10,
            "tokens_predicted": 20,
            "stop_type": "stop",
        }
        mock_resp.raise_for_status = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        provider.client = mock_client
        resp = await provider.generate(llm_request)
        assert resp.content == "generated text"

    @pytest.mark.asyncio
    async def test_health_check_failure(self):
        from src.services.llm_providers.local_provider import LocalLLMProvider
        provider = LocalLLMProvider.__new__(LocalLLMProvider)
        provider.base_url = "http://localhost:8080"
        provider.client = AsyncMock()
        provider.client.get = AsyncMock(side_effect=Exception("connection refused"))
        result = await provider.health_check()
        assert result["healthy"] is False

    @pytest.mark.asyncio
    async def test_list_models_fallback(self):
        from src.services.llm_providers.local_provider import LocalLLMProvider
        provider = LocalLLMProvider.__new__(LocalLLMProvider)
        provider.base_url = "http://localhost:8080"
        provider.default_model = "local"
        provider.client = AsyncMock()
        provider.client.get = AsyncMock(side_effect=Exception("fail"))
        models = await provider.list_models()
        assert models == ["local"]
