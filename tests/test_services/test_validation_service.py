"""
Tests for ValidationService.
"""

import pytest

from src.domain import CourseProfile, DomainPack, Jurisdiction, register_domain_pack
from src.services.validation_service import ValidationService


def _token(value: str) -> str:
    return "_".join(str(value).strip().lower().replace("-", " ").split())


def _register_validation_test_pack(
    key: str = "validation_test_tort",
    *,
    course_profiles=None,
    validation_overlay=None,
) -> None:
    aliases = {
        "negligence": "negligence",
        "duty_of_care": "duty_of_care",
        "duty care": "duty_of_care",
        "duty of care": "duty_of_care",
        "local_duty": "local_duty",
        "local duty": "local_duty",
    }

    def canonicalize(topic: str) -> str:
        normalized = _token(topic)
        return aliases.get(normalized, normalized)

    register_domain_pack(
        DomainPack(
            key=key,
            display_name="Validation Test Tort Law",
            jurisdiction=Jurisdiction(
                key="test",
                display_name="Testland",
                aliases=("testland",),
            ),
            law_domain="tort",
            canonicalize_topic=canonicalize,
            is_supported_topic=lambda topic: canonicalize(topic)
            in {"negligence", "duty_of_care", "local_duty"},
            topic_keys=("negligence", "duty_of_care", "local_duty"),
            topic_aliases={
                _token(alias): canonical for alias, canonical in aliases.items()
            },
            subject_label="Tort Law",
            course_profiles=course_profiles or {},
            validation_overlay=validation_overlay or {},
        )
    )


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

    def test_validate_topic_inclusion_returns_canonical_topics(
        self, validation_service
    ):
        """Topic outputs should use canonical tort topic keys."""
        text = "The defendant breached the duty of care and acted negligently."
        result = validation_service.validate_topic_inclusion(
            text, required_topics=["duty of care", "negligence"]
        )

        assert "duty_of_care" in result["topics_found"]
        assert "duty of care" not in result["topics_found"]

    def test_validate_topic_inclusion_normalizes_boundary_topic_variants(
        self, validation_service
    ):
        """Boundary variants (case/space/underscore) should normalize consistently."""
        text = "The defendant owed a duty of care and was negligent in supervision."
        result = validation_service.validate_topic_inclusion(
            text,
            required_topics=["Duty Of Care", "duty_of_care", "NEGLIGENCE"],
        )

        assert "duty_of_care" in result["topics_found"]
        assert "negligence" in result["topics_found"]
        assert result["topics_missing"] == []

    def test_validate_topic_inclusion_uses_registered_pack_overlay(
        self, validation_service
    ):
        """Custom packs should supply their own topic keyword overlay."""
        _register_validation_test_pack(
            "validation_overlay_tort",
            validation_overlay={
                "topic_keywords": {"local_duty": ["local duty marker"]}
            },
        )

        result = validation_service.validate_topic_inclusion(
            "The record contains a local duty marker and no SG-specific doctrine.",
            required_topics=["local duty"],
            corpus_pack="validation_overlay_tort",
        )

        assert result["passed"] is True
        assert result["topics_found"] == ["local_duty"]

    def test_validate_topic_inclusion_uses_course_profile_threshold(
        self, validation_service
    ):
        profile = CourseProfile(
            key="strict_profile",
            display_name="Strict Profile",
            corpus_pack_key="profile_validation_tort",
            syllabus_topics=("local_duty", "negligence"),
            validation_overlay={"topic_coverage_threshold": 1.0},
            data_backed=True,
        )
        _register_validation_test_pack(
            "profile_validation_tort",
            course_profiles={"strict_profile": profile},
            validation_overlay={
                "topic_coverage_threshold": 0.5,
                "topic_keywords": {
                    "local_duty": ["local duty marker"],
                    "negligence": ["negligent marker"],
                },
            },
        )

        result = validation_service.validate_topic_inclusion(
            "The record contains a local duty marker.",
            required_topics=["local duty", "negligence"],
            corpus_pack="profile_validation_tort",
            course_profile="strict_profile",
        )

        assert result["passed"] is False
        assert result["coverage_threshold"] == 1.0
        assert result["coverage_ratio"] == 0.5

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

    def test_validate_model_answer_reports_irac_issue_and_citation_quality(
        self, validation_service
    ):
        answer = """
        Issue: Whether the defendant owed a duty of care in negligence.
        Rule: Spandeck Engineering (S) Pte Ltd v Defence Science & Technology Agency [2007] SGCA 37 sets out factual foreseeability, proximity, and policy.
        Application: The claimant was directly affected by the defendant's unsafe premises, so proximity and breach should be analysed on the facts.
        Conclusion: The claimant has an arguable negligence claim if causation and damage are proved.
        """

        report = validation_service.validate_model_answer(
            answer,
            expected_issues=["negligence", "duty_of_care"],
            corpus_pack="sg_tort",
        )

        assert report["passed"] is True
        assert report["answer_quality_score"] >= 7.0
        assert report["checks"]["irac_structure"]["passed"] is True
        assert report["checks"]["expected_issues"]["missing_issues"] == []
        assert report["checks"]["citation_support"]["unsupported_citations"] == []
        assert report["summary"]["hypothetical_quality_separate"] is True

    def test_validate_model_answer_flags_missing_false_and_unsupported_diagnostics(
        self, validation_service
    ):
        answer = """
        Issue: Whether negligence or battery applies.
        Rule: Made Up v Citation [2099] SGCA 999 says the defendant always pays.
        Application: The answer discusses only negligent conduct.
        Conclusion: The claimant wins.
        """

        report = validation_service.validate_model_answer(
            answer,
            expected_issues=["negligence", "defamation"],
            corpus_pack="sg_tort",
        )

        diagnostics = report["diagnostics"]
        assert report["passed"] is False
        assert "defamation" in diagnostics["missing_issues"]
        assert "battery" in diagnostics["false_issues"]
        assert diagnostics["unsupported_citations"] == [
            "Made Up v Citation [2099] SGCA 999"
        ]
        assert any(
            "Address the expected issue" in item for item in diagnostics["feedback"]
        )

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

    def test_validate_hypothetical_fast_mode(self, validation_service):
        """Fast mode should run topic+party checks only."""
        text = (
            "In Singapore, Mr. John Smith was negligent and breached his duty of care "
            "towards Ms. Jane Doe. ABC Pte Ltd was involved in the incident."
        )

        result = validation_service.validate_hypothetical(
            text=text,
            required_topics=["negligence", "duty of care"],
            expected_parties=2,
            fast_mode=True,
        )

        assert result["summary"]["mode"] == "fast"
        assert "party_count" in result["checks"]
        assert "topic_inclusion" in result["checks"]
        assert "word_count" not in result["checks"]
        assert "singapore_context" not in result["checks"]

    def test_validate_hypothetical_receives_non_sg_jurisdiction_context(
        self, validation_service
    ):
        """Non-SG validation should carry jurisdiction without SG context gate."""
        _register_validation_test_pack("test_tort")
        text = """
        Alice Smith sued Bob Jones after a negligent warehouse accident. The defendant
        breached a duty of care and caused the claimant's injury. The parties disputed
        liability, damages, and whether the claimant failed to mitigate loss.
        """ * 10

        result = validation_service.validate_hypothetical(
            text=text,
            required_topics=["negligence", "duty of care"],
            expected_parties=2,
            corpus_pack="test_tort",
            jurisdiction="test",
            subject="tort",
            law_domain="tort",
        )

        assert result["summary"]["jurisdiction"] == "test"
        assert result["checks"]["jurisdiction_context"]["jurisdiction"] == "test"

    def test_validate_legal_realism_scores_high_with_singapore_context(
        self, validation_service
    ):
        """Legal realism should score strongly when SG context/procedure cues are present."""
        text = (
            "In Singapore, the plaintiff filed a claim in the High Court after a collision "
            "along Orchard Road. The defendant denied liability, but subsequently admitted "
            "breach of duty and causation in 2024 after events that began in 2022."
        )

        result = validation_service.validate_legal_realism(text)

        assert result["passed"] is True
        assert result["realism_score"] >= 0.6
        assert result["components"]["singapore_context_score"] > 0.0
        assert "singapore" in result["evidence"]["singapore_context"]

    def test_validate_legal_realism_flags_missing_singapore_context(
        self, validation_service
    ):
        """Legal realism should fail when scenario lacks Singapore context signals."""
        text = (
            "The claimant alleged negligence against the defendant after an accident. "
            "The parties argued about breach and damages, but no jurisdictional context "
            "or local venue details were provided."
        )

        result = validation_service.validate_legal_realism(text)

        assert result["passed"] is False
        assert result["realism_score"] < 0.6
        assert result["components"]["singapore_context_score"] == 0.0

    def test_validate_hypothetical_includes_legal_realism_component(
        self, validation_service
    ):
        """Full validation output should expose legal realism checks and scoring."""
        text = (
            "In Singapore, the plaintiff sued the defendant over negligence at a Marina Bay "
            "construction site. The chronology was: incident in 2022, medical treatment in "
            "2023, and High Court hearing in 2024. The duty of care, breach, and causation "
            "issues were pleaded."
        )

        result = validation_service.validate_hypothetical(
            text=text,
            required_topics=["negligence", "duty of care", "causation"],
            expected_parties=2,
            law_domain="tort",
        )

        assert "legal_realism" in result["checks"]
        assert "realism_score" in result["checks"]["legal_realism"]
