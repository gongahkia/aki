"""
Tests for ValidationService.
"""

import pytest

from src.services.validation_service import ValidationService


class TestValidationService:
    """Test ValidationService."""

    @pytest.fixture
    def validation_service(self):
        """Create ValidationService instance for testing."""
        return ValidationService()

    def test_validate_party_count_success(self, validation_service):
        """Test party count validation with correct parties."""
        text = """
        Mr. John Smith owns a restaurant in Singapore. He employed Ms. Jane Doe as a chef.
        ABC Pte Ltd supplied raw ingredients to the restaurant.
        """
        result = validation_service.validate_party_count(text, expected_count=3)

        assert result["passed"] is True
        assert result["actual_count"] >= 3
        assert "entities" in result

    def test_validate_party_count_failure(self, validation_service):
        """Test party count validation with insufficient parties."""
        text = "John went to a store."
        result = validation_service.validate_party_count(text, expected_count=5)

        assert result["passed"] is False
        assert result["actual_count"] < 5

    def test_validate_topic_inclusion_success(self, validation_service):
        """Test topic inclusion with all topics present."""
        text = """
        The defendant was negligent in maintaining the premises, breaching the duty of care
        owed to visitors. This negligence directly caused the plaintiff's injuries.
        """
        result = validation_service.validate_topic_inclusion(
            text, required_topics=["negligence", "duty of care", "causation"]
        )

        assert result["passed"] is True
        assert len(result["topics_found"]) >= 2
        assert result["coverage_ratio"] >= 0.7

    def test_validate_topic_inclusion_partial(self, validation_service):
        """Test topic inclusion with partial coverage."""
        text = (
            "The defendant committed battery by intentionally touching the plaintiff."
        )
        result = validation_service.validate_topic_inclusion(
            text, required_topics=["battery", "negligence", "defamation"]
        )

        # Should pass with >70% coverage (1/3 = 33%, but battery is there)
        assert "battery" in result["topics_found"]
        assert "negligence" in result["topics_missing"]

    def test_validate_topic_inclusion_returns_canonical_topics(self, validation_service):
        """Topic outputs should use canonical tort topic keys."""
        text = "The defendant breached the duty of care and acted negligently."
        result = validation_service.validate_topic_inclusion(
            text, required_topics=["duty of care", "negligence"]
        )

        assert "duty_of_care" in result["topics_found"]
        assert "duty of care" not in result["topics_found"]

    def test_validate_word_count_success(self, validation_service):
        """Test word count validation with appropriate length."""
        text = " ".join(["word"] * 1000)  # 1000 words
        result = validation_service.validate_word_count(
            text, min_words=800, max_words=1500
        )

        assert result["passed"] is True
        assert result["word_count"] == 1000

    def test_validate_word_count_too_short(self, validation_service):
        """Test word count validation with insufficient words."""
        text = "Too short"
        result = validation_service.validate_word_count(
            text, min_words=800, max_words=1500
        )

        assert result["passed"] is False
        assert result["word_count"] < 800

    def test_validate_singapore_context_success(self, validation_service):
        """Test Singapore context validation with valid references."""
        text = """
        The incident occurred at Marina Bay in Singapore. The plaintiff paid S$500 in damages.
        The case was heard in the High Court of Singapore.
        """
        result = validation_service.validate_singapore_context(text)

        assert result["passed"] is True
        assert result["singapore_mentions"] > 0
        assert len(result["evidence"]) > 0

    def test_validate_singapore_context_failure(self, validation_service):
        """Test Singapore context validation with no references."""
        text = "A generic legal scenario with no specific location."
        result = validation_service.validate_singapore_context(text)

        assert result["passed"] is False
        assert result["singapore_mentions"] == 0

    def test_validate_hypothetical_complete(self, validation_service):
        """Test complete hypothetical validation."""
        text = """
        In Singapore, Mr. John Smith, a restaurant owner, employed Ms. Jane Doe as a chef.
        ABC Pte Ltd supplied ingredients. The restaurant owner was negligent in maintaining
        the kitchen, breaching the duty of care owed to employees. This negligence caused
        Ms. Doe to slip and injure herself. The injury resulted from the owner's failure
        to meet the standard of care expected of reasonable restaurant operators. The
        causation was clear, as the wet floor directly led to the injury. The incident
        occurred at Marina Bay area in Singapore, where the restaurant is located.
        """ * 10  # Make it longer

        result = validation_service.validate_hypothetical(
            text=text,
            required_topics=["negligence", "duty of care", "causation"],
            expected_parties=3,
            law_domain="tort",
        )

        assert "passed" in result
        assert "overall_score" in result
        assert result["overall_score"] >= 0.0
        assert result["overall_score"] <= 10.0
        assert "checks" in result
        assert "party_count" in result["checks"]
        assert "topic_inclusion" in result["checks"]

    def test_calculate_overall_score(self, validation_service):
        """Test overall score calculation."""
        validation_results = {
            "party_count": {"passed": True},
            "topic_inclusion": {"passed": True, "coverage_ratio": 1.0},
            "word_count": {"passed": True},
            "singapore_context": {"passed": True},
        }

        score, passed = validation_service.calculate_overall_score(validation_results)

        assert score >= 7.0  # Should pass with all checks passing
        assert passed is True
        assert score <= 10.0

    def test_calculate_overall_score_failure(self, validation_service):
        """Test overall score calculation with failures."""
        validation_results = {
            "party_count": {"passed": False},
            "topic_inclusion": {"passed": False, "coverage_ratio": 0.0},
            "word_count": {"passed": False},
            "singapore_context": {"passed": False},
        }

        score, passed = validation_service.calculate_overall_score(validation_results)

        assert score < 7.0  # Should fail
        assert passed is False
        assert score >= 0.0
