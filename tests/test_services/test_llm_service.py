"""
Tests for LLM Service.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from src.services.llm_service import (
    LLMService,
    OllamaProvider,
    OpenAIProvider,
    LLMRequest,
    LLMResponse,
    LLMServiceError,
)


class TestLLMRequest:
    """Test LLMRequest model."""

    def test_llm_request_creation(self):
        """Test LLMRequest creation with valid data."""
        request = LLMRequest(
            prompt="Test prompt",
            system_prompt="Test system prompt",
            temperature=0.7,
            max_tokens=1000,
        )

        assert request.prompt == "Test prompt"
        assert request.system_prompt == "Test system prompt"
        assert request.temperature == 0.7
        assert request.max_tokens == 1000
        assert request.stream is False

    def test_llm_request_validation(self):
        """Test LLMRequest validation."""
        # Test temperature bounds
        with pytest.raises(ValueError):
            LLMRequest(prompt="test", temperature=3.0)

        with pytest.raises(ValueError):
            LLMRequest(prompt="test", temperature=-1.0)

        # Test max_tokens bounds
        with pytest.raises(ValueError):
            LLMRequest(prompt="test", max_tokens=0)


class TestLLMResponse:
    """Test LLMResponse model."""

    def test_llm_response_creation(self):
        """Test LLMResponse creation."""
        response = LLMResponse(
            content="Test response",
            model="llama2:7b",
            usage={"total_tokens": 100},
            finish_reason="stop",
            response_time=1.5,
        )

        assert response.content == "Test response"
        assert response.model == "llama2:7b"
        assert response.usage["total_tokens"] == 100
        assert response.finish_reason == "stop"
        assert response.response_time == 1.5


class TestOllamaProvider:
    """Test OllamaProvider."""

    @pytest.fixture
    def ollama_provider(self):
        """Create OllamaProvider instance for testing."""
        return OllamaProvider(base_url="http://localhost:11434", timeout=10)

    @pytest.mark.asyncio
    async def test_ollama_generate_success(self, ollama_provider, mock_llm_response):
        """Test successful Ollama generation."""
        mock_response_data = {
            "response": "Test response",
            "model": "llama2:7b",
            "prompt_eval_count": 100,
            "eval_count": 50,
            "done": True,
            "load_duration": 1000000000,
            "prompt_eval_duration": 500000000,
            "eval_duration": 2000000000,
            "total_duration": 3500000000,
        }

        with patch.object(ollama_provider.client, "post") as mock_post:
            mock_post.return_value.json.return_value = mock_response_data
            mock_post.return_value.raise_for_status.return_value = None

            request = LLMRequest(prompt="Test prompt")
            response = await ollama_provider.generate(request)

            assert response.content == "Test response"
            assert response.model == "llama2:7b"
            assert response.usage["total_tokens"] == 150
            assert response.finish_reason == "stop"

    @pytest.mark.asyncio
    async def test_ollama_generate_http_error(self, ollama_provider):
        """Test Ollama generation with HTTP error."""
        with patch.object(ollama_provider.client, "post") as mock_post:
            mock_post.side_effect = httpx.HTTPError("Connection error")

            request = LLMRequest(prompt="Test prompt")

            with pytest.raises(LLMServiceError):
                await ollama_provider.generate(request)

    @pytest.mark.asyncio
    async def test_ollama_health_check_success(self, ollama_provider):
        """Test successful Ollama health check."""
        with patch.object(ollama_provider.client, "get") as mock_get:
            mock_get.return_value.status_code = 200

            result = await ollama_provider.health_check()
            assert result is True

    @pytest.mark.asyncio
    async def test_ollama_health_check_failure(self, ollama_provider):
        """Test failed Ollama health check."""
        with patch.object(ollama_provider.client, "get") as mock_get:
            mock_get.side_effect = httpx.HTTPError("Connection error")

            result = await ollama_provider.health_check()
            assert result is False


class TestOpenAIProvider:
    """Test OpenAIProvider."""

    @pytest.fixture
    def openai_provider(self):
        """Create OpenAIProvider instance for testing."""
        return OpenAIProvider(api_key="test-key", timeout=10)

    @pytest.mark.asyncio
    async def test_openai_generate_success(self, openai_provider):
        """Test successful OpenAI generation."""
        mock_response_data = {
            "choices": [
                {"message": {"content": "Test response"}, "finish_reason": "stop"}
            ],
            "model": "gpt-3.5-turbo",
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 150,
            },
        }

        with patch.object(openai_provider.client, "post") as mock_post:
            mock_post.return_value.json.return_value = mock_response_data
            mock_post.return_value.raise_for_status.return_value = None

            request = LLMRequest(prompt="Test prompt")
            response = await openai_provider.generate(request)

            assert response.content == "Test response"
            assert response.model == "gpt-3.5-turbo"
            assert response.usage["total_tokens"] == 150
            assert response.finish_reason == "stop"

    @pytest.mark.asyncio
    async def test_openai_health_check_success(self, openai_provider):
        """Test successful OpenAI health check."""
        with patch.object(openai_provider.client, "get") as mock_get:
            mock_get.return_value.status_code = 200

            result = await openai_provider.health_check()
            assert result is True


class TestLLMService:
    """Test LLMService."""

    @pytest.fixture
    def llm_service(self):
        """Create LLMService instance for testing."""
        service = LLMService()
        # Mock the providers
        service._providers = {
            "ollama": AsyncMock(spec=OllamaProvider),
            "openai": AsyncMock(spec=OpenAIProvider),
        }
        service._default_provider = "ollama"
        return service

    @pytest.mark.asyncio
    async def test_generate_with_default_provider(self, llm_service, mock_llm_response):
        """Test generation with default provider."""
        llm_service._providers["ollama"].generate.return_value = mock_llm_response

        request = LLMRequest(prompt="Test prompt")
        response = await llm_service.generate(request)

        assert response == mock_llm_response
        llm_service._providers["ollama"].generate.assert_called_once_with(request)

    @pytest.mark.asyncio
    async def test_generate_with_specific_provider(
        self, llm_service, mock_llm_response
    ):
        """Test generation with specific provider."""
        llm_service._providers["openai"].generate.return_value = mock_llm_response

        request = LLMRequest(prompt="Test prompt")
        response = await llm_service.generate(request, provider="openai")

        assert response == mock_llm_response
        llm_service._providers["openai"].generate.assert_called_once_with(request)

    @pytest.mark.asyncio
    async def test_generate_with_invalid_provider(self, llm_service):
        """Test generation with invalid provider."""
        request = LLMRequest(prompt="Test prompt")

        with pytest.raises(LLMServiceError):
            await llm_service.generate(request, provider="invalid")

    @pytest.mark.asyncio
    async def test_health_check_all_providers(self, llm_service):
        """Test health check for all providers."""
        llm_service._providers["ollama"].health_check.return_value = True
        llm_service._providers["openai"].health_check.return_value = False

        result = await llm_service.health_check()

        assert result == {"ollama": True, "openai": False}

    @pytest.mark.asyncio
    async def test_health_check_specific_provider(self, llm_service):
        """Test health check for specific provider."""
        llm_service._providers["ollama"].health_check.return_value = True

        result = await llm_service.health_check(provider="ollama")

        assert result == {"ollama": True}

    @pytest.mark.asyncio
    async def test_list_models(self, llm_service):
        """Test listing available models."""
        models = await llm_service.list_models()

        assert "ollama" in models
        assert "openai" in models
        assert isinstance(models["ollama"], list)
        assert isinstance(models["openai"], list)

    @pytest.mark.asyncio
    async def test_close(self, llm_service):
        """Test closing all providers."""
        await llm_service.close()

        llm_service._providers["ollama"].close.assert_called_once()
        llm_service._providers["openai"].close.assert_called_once()
