"""
Tests for DatabaseService.
"""

import tempfile
from pathlib import Path

import pytest
import pytest_asyncio

from src.services.database_service import (
    DatabaseService,
    GenerationFeedback,
    GenerationReport,
)


class TestDatabaseService:
    """Test DatabaseService."""

    @pytest_asyncio.fixture
    async def database_service(self):
        """Create DatabaseService instance with temporary database."""
        # Use temporary database for testing
        temp_dir = tempfile.mkdtemp()
        db_path = Path(temp_dir) / "test_jikai.db"
        service = DatabaseService(str(db_path))
        yield service
        # Cleanup
        if db_path.exists():
            db_path.unlink()

    @pytest.mark.asyncio
    async def test_database_initialization(self, database_service):
        """Test database initialization."""
        assert database_service._db_path.exists()

        health = await database_service.health_check()
        assert health["database_exists"] is True
        assert health["connection_ok"] is True
        assert health["record_count"] == 0

    @pytest.mark.asyncio
    async def test_save_generation(self, database_service):
        """Test saving generation to database."""
        request_data = {
            "topics": ["negligence", "duty of care"],
            "law_domain": "tort",
            "number_parties": 3,
            "complexity_level": "intermediate",
        }

        response_data = {
            "hypothetical": "Test hypothetical text...",
            "analysis": "Test analysis...",
            "generation_time": 15.5,
            "validation_results": {"passed": True, "quality_score": 8.5},
            "metadata": {"generation_timestamp": "2025-01-01T00:00:00"},
        }

        record_id = await database_service.save_generation(request_data, response_data)

        assert record_id > 0

        # Verify saved
        health = await database_service.health_check()
        assert health["record_count"] == 1

    @pytest.mark.asyncio
    async def test_get_recent_generations(self, database_service):
        """Test retrieving recent generations."""
        # Save multiple generations
        for i in range(5):
            request_data = {
                "topics": [f"topic_{i}"],
                "law_domain": "tort",
                "number_parties": 2,
                "complexity_level": "beginner",
            }
            response_data = {
                "hypothetical": f"Hypothetical {i}",
                "analysis": f"Analysis {i}",
                "generation_time": 10.0 + i,
                "validation_results": {"passed": True, "quality_score": 7.0 + i},
                "metadata": {"generation_timestamp": f"2025-01-0{i+1}T00:00:00"},
            }
            await database_service.save_generation(request_data, response_data)

        # Get recent generations
        recent = await database_service.get_recent_generations(limit=3)

        assert len(recent) == 3
        assert "timestamp" in recent[0]
        assert "request" in recent[0]
        assert "response" in recent[0]

    @pytest.mark.asyncio
    async def test_get_statistics(self, database_service):
        """Test getting statistics."""
        # Save some generations
        for i in range(10):
            request_data = {
                "topics": ["negligence"],
                "law_domain": "tort",
                "number_parties": 2,
                "complexity_level": "intermediate",
            }
            response_data = {
                "hypothetical": f"Test {i}",
                "analysis": "Analysis",
                "generation_time": 10.0 + i,
                "validation_results": {"passed": i % 2 == 0, "quality_score": 7.0},
                "metadata": {"generation_timestamp": f"2025-01-01T00:0{i}:00"},
            }
            await database_service.save_generation(request_data, response_data)

        stats = await database_service.get_statistics()

        assert stats["total_generations"] == 10
        assert stats["average_generation_time"] > 0
        assert 0 <= stats["success_rate"] <= 100
        assert stats["average_quality_score"] > 0

    @pytest.mark.asyncio
    async def test_search_by_topics(self, database_service):
        """Test searching by topics."""
        # Save generations with different topics
        topics_sets = [
            ["negligence", "duty of care"],
            ["battery", "assault"],
            ["negligence", "causation"],
        ]

        for topics in topics_sets:
            request_data = {
                "topics": topics,
                "law_domain": "tort",
                "number_parties": 2,
                "complexity_level": "intermediate",
            }
            response_data = {
                "hypothetical": f"Hypothetical about {topics}",
                "analysis": "Analysis",
                "generation_time": 12.0,
                "validation_results": {"passed": True, "quality_score": 8.0},
                "metadata": {"generation_timestamp": "2025-01-01T00:00:00"},
            }
            await database_service.save_generation(request_data, response_data)

        # Search for 'negligence'
        results = await database_service.search_by_topics(["negligence"], limit=10)

        assert len(results) == 2  # Two entries with 'negligence'
        assert "hypothetical" in results[0]
        assert "topics" in results[0]

    @pytest.mark.asyncio
    async def test_save_generation_report_and_feedback(self, database_service):
        """Test saving report and feedback linked to a generation."""
        generation_id = await database_service.save_generation(
            request_data={
                "topics": ["negligence"],
                "law_domain": "tort",
                "number_parties": 2,
                "complexity_level": "intermediate",
            },
            response_data={
                "hypothetical": "Test hypothetical text...",
                "analysis": "Test analysis...",
                "generation_time": 11.0,
                "validation_results": {"passed": True, "quality_score": 8.0},
                "metadata": {"generation_timestamp": "2025-01-01T00:00:00"},
            },
        )

        report_id = await database_service.save_generation_report(
            GenerationReport(
                generation_id=generation_id,
                issue_types=["topic_mismatch"],
                comment="Regenerate with stricter topic coverage",
                is_locked=True,
            )
        )
        assert report_id > 0

        feedback_id = await database_service.save_generation_feedback(
            GenerationFeedback(
                report_id=report_id,
                generation_id=generation_id,
                feedback_text="Previous attempt missed causation details.",
            )
        )
        assert feedback_id > 0

        reports = await database_service.get_generation_reports(generation_id)
        assert len(reports) == 1
        assert reports[0].issue_types == ["topic_mismatch"]
        assert reports[0].is_locked is True

    @pytest.mark.asyncio
    async def test_generation_report_foreign_key_enforced(self, database_service):
        """Report insert should fail when generation row is missing."""
        with pytest.raises(Exception):
            await database_service.save_generation_report(
                GenerationReport(
                    generation_id=999999,
                    issue_types=["quality_fail"],
                    comment="No linked generation should fail.",
                )
            )

    @pytest.mark.asyncio
    async def test_get_generation_by_id(self, database_service):
        """Generation rows should be retrievable by primary key."""
        generation_id = await database_service.save_generation(
            request_data={
                "topics": ["negligence"],
                "law_domain": "tort",
                "number_parties": 2,
                "complexity_level": "intermediate",
            },
            response_data={
                "hypothetical": "Test hypothetical text...",
                "analysis": "Test analysis...",
                "generation_time": 11.0,
                "validation_results": {"passed": True, "quality_score": 8.0},
                "metadata": {"generation_timestamp": "2025-01-01T00:00:00"},
            },
        )
        row = await database_service.get_generation_by_id(generation_id)

        assert row is not None
        assert row["id"] == generation_id
        assert row["request"]["topics"] == ["negligence"]

    @pytest.mark.asyncio
    async def test_build_regeneration_feedback_context(self, database_service):
        """Feedback context should include report issue types and comments."""
        generation_id = await database_service.save_generation(
            request_data={
                "topics": ["negligence"],
                "law_domain": "tort",
                "number_parties": 2,
                "complexity_level": "intermediate",
            },
            response_data={
                "hypothetical": "Test hypothetical text...",
                "analysis": "Test analysis...",
                "generation_time": 11.0,
                "validation_results": {"passed": True, "quality_score": 8.0},
                "metadata": {"generation_timestamp": "2025-01-01T00:00:00"},
            },
        )
        report_id = await database_service.save_generation_report(
            GenerationReport(
                generation_id=generation_id,
                issue_types=["topic_mismatch"],
                comment="Missing causation detail.",
                is_locked=True,
            )
        )
        await database_service.save_generation_feedback(
            GenerationFeedback(
                report_id=report_id,
                generation_id=generation_id,
                feedback_text="Increase factual detail around duty.",
            )
        )

        context = await database_service.build_regeneration_feedback_context(
            generation_id
        )
        assert "topic_mismatch" in context
        assert "Missing causation detail." in context
        assert "Increase factual detail around duty." in context

    @pytest.mark.asyncio
    async def test_generation_report_update_is_blocked(self, database_service):
        """Report comments are immutable and cannot be edited."""
        with pytest.raises(PermissionError):
            await database_service.update_generation_report_comment(
                report_id=1, comment="new comment"
            )

    @pytest.mark.asyncio
    async def test_generation_report_delete_is_blocked(self, database_service):
        """Reports are append-only and cannot be deleted."""
        with pytest.raises(PermissionError):
            await database_service.delete_generation_report(report_id=1)
