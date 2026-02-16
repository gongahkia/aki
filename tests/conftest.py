"""
Pytest configuration and fixtures for Jikai tests.
"""

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from src.services.llm_service import LLMResponse, LLMService


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_corpus_file():
    """Create a temporary corpus file for testing."""
    sample_corpus = [
        {
            "text": "Sample tort law hypothetical involving negligence and duty of care.",
            "topic": ["negligence", "duty of care", "causation"],
            "metadata": {"complexity": "intermediate"},
        },
        {
            "text": "Another hypothetical involving battery and assault claims.",
            "topic": ["battery", "assault", "false imprisonment"],
            "metadata": {"complexity": "advanced"},
        },
    ]

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(sample_corpus, f)
        temp_path = Path(f.name)

    yield temp_path

    # Cleanup
    temp_path.unlink(missing_ok=True)


@pytest.fixture
def mock_llm_response():
    """Mock LLM response for testing."""
    return LLMResponse(
        content="This is a generated hypothetical scenario involving negligence and duty of care.",
        model="llama2:7b",
        usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        finish_reason="stop",
        response_time=2.5,
        metadata={"load_duration": 1000000000},
    )


@pytest.fixture
def mock_corpus_entries():
    """Mock corpus entries for testing."""
    try:
        from src.services.corpus_service import HypotheticalEntry
    except Exception:
        pytest.skip("chromadb not available")
    return [
        HypotheticalEntry(
            id="1",
            text="Sample tort law hypothetical involving negligence and duty of care.",
            topics=["negligence", "duty of care", "causation"],
            metadata={"complexity": "intermediate"},
        ),
        HypotheticalEntry(
            id="2",
            text="Another hypothetical involving battery and assault claims.",
            topics=["battery", "assault", "false imprisonment"],
            metadata={"complexity": "advanced"},
        ),
    ]


@pytest.fixture
def mock_llm_service():
    """Mock LLM service for testing."""
    service = AsyncMock(spec=LLMService)
    service.generate = AsyncMock()
    service.health_check = AsyncMock(return_value={"ollama": True})
    service.close = AsyncMock()
    return service


@pytest.fixture
def mock_corpus_service():
    """Mock corpus service for testing."""
    try:
        from src.services.corpus_service import CorpusService
    except Exception:
        pytest.skip("chromadb not available")
    service = AsyncMock(spec=CorpusService)
    service.load_corpus = AsyncMock()
    service.query_relevant_hypotheticals = AsyncMock()
    service.extract_all_topics = AsyncMock(
        return_value=[
            "negligence",
            "duty of care",
            "causation",
            "battery",
            "assault",
            "false imprisonment",
        ]
    )
    service.add_hypothetical = AsyncMock(return_value="new_id")
    service.health_check = AsyncMock(
        return_value={"local_corpus": True, "total_entries": 2}
    )
    return service


@pytest.fixture
def sample_generation_request():
    """Sample generation request for testing."""
    return {
        "topics": ["negligence", "duty of care"],
        "law_domain": "tort",
        "number_parties": 3,
        "complexity_level": "intermediate",
        "sample_size": 2,
    }


@pytest.fixture
def sample_corpus_query():
    """Sample corpus query for testing."""
    if not _HAS_CORPUS:
        pytest.skip("chromadb/corpus_service not available")
    return CorpusQuery(
        topics=["negligence", "duty of care"], sample_size=2, min_topic_overlap=1
    )


@pytest.fixture
def test_settings():
    """Test settings configuration."""
    return {
        "app_name": "Jikai Test",
        "app_version": "2.0.0-test",
        "environment": "test",
        "api": {"host": "0.0.0.0", "port": 8000, "debug": True},
        "llm": {"provider": "ollama", "model_name": "llama2:7b", "temperature": 0.7},
        "database": {"chroma_host": "localhost", "chroma_port": 8000},
    }


@pytest.fixture(autouse=True)
def setup_test_environment(monkeypatch, test_settings):
    """Set up test environment variables."""
    # Mock environment variables
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("API_DEBUG", "true")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")

    # Mock settings
    for key, value in test_settings.items():
        if isinstance(value, dict):
            for sub_key, sub_value in value.items():
                monkeypatch.setenv(f"{key.upper()}_{sub_key.upper()}", str(sub_value))
        else:
            monkeypatch.setenv(key.upper(), str(value))


@pytest.fixture
def mock_validation_response():
    """Mock validation response for testing."""
    return {
        "adherence_check": {
            "overall_compliance": "PASS",
            "score": 8.5,
            "full_response": "Validation passed with high quality",
        },
        "similarity_check": {
            "overall_originality": "PASS",
            "score": 9.0,
            "full_response": "Content is original and distinct",
        },
        "quality_score": 8.75,
        "passed": True,
    }
