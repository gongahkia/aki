"""
Validation Service for deterministic hypothetical validation.
Replaces expensive LLM-based validation with fast, reliable programmatic checks.
"""

import re
from typing import Any, Dict, List, Tuple

import structlog

from ..domain import all_tort_topic_keys, canonicalize_topic

logger = structlog.get_logger(__name__)


class ValidationService:
    """Service for deterministic validation of legal hypotheticals."""

    def __init__(self):
        # Common person/entity indicators
        self._person_indicators = [
            r"\b[A-Z][a-z]+\s+[A-Z][a-z]+\b",  # First Last name
            r"\b(?:Mr|Mrs|Ms|Dr|Prof)\.?\s+[A-Z][a-z]+",  # Titled names
            r"\b[A-Z][a-z]+\b(?:\s+(?:Pte|Ltd|Inc|Corp|LLC|LLP))",  # Companies
        ]

        # Singapore tort law keywords by topic
        raw_topic_keywords = {
            "negligence": [
                "negligent",
                "negligence",
                "duty",
                "breach",
                "reasonable person",
                "standard of care",
            ],
            "duty of care": [
                "duty of care",
                "duty",
                "owed",
                "responsibility",
                "obligation",
            ],
            "standard of care": ["standard", "reasonable", "prudent", "expected"],
            "causation": ["causation", "caused", "resulting", "consequence", "led to"],
            "remoteness": ["remote", "foreseeable", "foreseeability", "proximate"],
            "battery": [
                "battery",
                "intentional",
                "contact",
                "touching",
                "physical force",
            ],
            "assault": ["assault", "threat", "fear", "apprehension", "imminent"],
            "false imprisonment": [
                "imprisonment",
                "confined",
                "restrained",
                "detained",
                "liberty",
            ],
            "defamation": [
                "defamation",
                "defamatory",
                "reputation",
                "slander",
                "libel",
            ],
            "private nuisance": [
                "nuisance",
                "interference",
                "enjoyment",
                "land",
                "property",
            ],
            "trespass to land": [
                "trespass",
                "entered",
                "land",
                "property",
                "without permission",
            ],
            "vicarious liability": [
                "vicarious",
                "employer",
                "employee",
                "course of employment",
            ],
            "strict liability": [
                "strict liability",
                "no fault",
                "absolute",
                "inherently dangerous",
            ],
            "harassment": ["harassment", "harass", "alarm", "distress"],
            "occupiers_liability": [
                "occupier",
                "visitor",
                "premises",
                "invitee",
                "licensee",
                "trespasser",
            ],
            "product_liability": [
                "manufacturer",
                "product",
                "defect",
                "consumer",
                "safety",
            ],
            "contributory_negligence": [
                "contributory",
                "claimant",
                "own fault",
                "contributed",
                "apportionment",
            ],
            "economic_loss": [
                "economic loss",
                "pure economic",
                "financial loss",
                "pecuniary",
            ],
            "psychiatric_harm": [
                "psychiatric",
                "nervous shock",
                "mental injury",
                "ptsd",
                "psychological",
            ],
            "employers_liability": [
                "employer",
                "workplace",
                "occupational",
                "safe system",
                "employee injury",
            ],
            "breach_of_statutory_duty": [
                "statutory duty",
                "statute",
                "breach of duty",
                "legislative",
                "regulation",
            ],
            "rylands_v_fletcher": [
                "rylands",
                "fletcher",
                "escape",
                "non-natural use",
                "accumulation",
            ],
            "consent_defence": [
                "consent",
                "volenti",
                "agreed",
                "assumption of risk",
                "willing",
            ],
            "illegality_defence": [
                "illegality",
                "ex turpi",
                "illegal act",
                "unlawful",
                "criminal",
            ],
            "limitation_periods": [
                "limitation",
                "time bar",
                "statute of limitations",
                "accrual",
                "prescribed period",
            ],
            "res_ipsa_loquitur": [
                "res ipsa",
                "speaks for itself",
                "inference",
                "control",
                "without explanation",
            ],
            "novus_actus_interveniens": [
                "novus actus",
                "intervening",
                "break in chain",
                "superseding cause",
                "new act",
            ],
            "volenti_non_fit_injuria": [
                "volenti",
                "voluntary assumption",
                "consent to risk",
                "willing participant",
            ],
        }
        normalized_keywords = self._normalize_topic_keywords(raw_topic_keywords)
        canonical_keys = all_tort_topic_keys()
        self._topic_keywords = {
            key: normalized_keywords.get(key, [key.replace("_", " ")])
            for key in canonical_keys
        }

    @staticmethod
    def _normalize_topic_keywords(
        topic_keywords: Dict[str, List[str]]
    ) -> Dict[str, List[str]]:
        """Normalize topic keyword map to canonical topic keys."""
        normalized: Dict[str, List[str]] = {}
        for raw_key, raw_keywords in topic_keywords.items():
            canonical_key = canonicalize_topic(raw_key)
            existing = normalized.setdefault(canonical_key, [])
            cleaned_keywords = []
            for keyword in raw_keywords:
                text = str(keyword).strip().lower()
                if text:
                    cleaned_keywords.append(text)
            # preserve insertion order while deduplicating
            for keyword in cleaned_keywords:
                if keyword not in existing:
                    existing.append(keyword)
        return normalized

    def validate_party_count(self, text: str, expected_count: int) -> Dict[str, Any]:
        """
        Count distinct parties in text using entity extraction.

        Returns:
            Dict with 'passed', 'actual_count', 'expected_count', 'entities'
        """
        try:
            # Extract potential entities
            entities = set()

            # Find capitalized names (simple NER)
            for pattern in self._person_indicators:
                matches = re.findall(pattern, text)
                entities.update(matches)

            # Remove common non-entity words
            common_words = {"Singapore", "Tort", "Law", "Court", "The", "A", "An"}
            entities = {
                e for e in entities if not any(word in e for word in common_words)
            }

            actual_count = len(entities)
            passed = actual_count >= expected_count  # Allow more parties than requested

            logger.info(
                "Party count validation",
                expected=expected_count,
                actual=actual_count,
                passed=passed,
            )

            return {
                "passed": passed,
                "expected_count": expected_count,
                "actual_count": actual_count,
                "entities": list(entities),
                "message": f"Found {actual_count} parties (expected {expected_count})",
            }

        except Exception as e:
            logger.error("Party count validation failed", error=str(e))
            return {
                "passed": False,
                "expected_count": expected_count,
                "actual_count": 0,
                "entities": [],
                "message": f"Validation error: {e}",
            }

    def validate_topic_inclusion(
        self, text: str, required_topics: List[str]
    ) -> Dict[str, Any]:
        """
        Check if required topics are present in text using keyword matching.

        Returns:
            Dict with 'passed', 'topics_found', 'topics_missing', 'coverage_ratio'
        """
        try:
            text_lower = text.lower()
            topics_found: List[str] = []
            topic_evidence: Dict[str, List[str]] = {}
            canonical_required_topics: List[str] = []
            seen_topics = set()

            for topic in required_topics:
                canonical = canonicalize_topic(topic)
                if canonical not in seen_topics:
                    seen_topics.add(canonical)
                    canonical_required_topics.append(canonical)

            for canonical_topic in canonical_required_topics:
                keywords = self._topic_keywords.get(
                    canonical_topic,
                    [canonical_topic.replace("_", " ")],
                )

                # Check if any keyword appears in text
                found_keywords = [kw for kw in keywords if kw in text_lower]

                if found_keywords:
                    topics_found.append(canonical_topic)
                    topic_evidence[canonical_topic] = found_keywords

            topics_missing = [
                t for t in canonical_required_topics if t not in topics_found
            ]
            coverage_ratio = (
                len(topics_found) / len(canonical_required_topics)
                if canonical_required_topics
                else 1.0
            )

            # Pass if at least 70% of topics are covered
            passed = coverage_ratio >= 0.7

            logger.info(
                "Topic inclusion validation",
                required=len(canonical_required_topics),
                found=len(topics_found),
                coverage=f"{coverage_ratio:.1%}",
                passed=passed,
            )

            return {
                "passed": passed,
                "topics_found": topics_found,
                "topics_missing": topics_missing,
                "coverage_ratio": coverage_ratio,
                "topic_evidence": topic_evidence,
                "message": f"Found {len(topics_found)}/{len(canonical_required_topics)} topics ({coverage_ratio:.0%} coverage)",
            }

        except Exception as e:
            logger.error("Topic inclusion validation failed", error=str(e))
            canonical_required_topics = [canonicalize_topic(topic) for topic in required_topics]
            return {
                "passed": False,
                "topics_found": [],
                "topics_missing": canonical_required_topics,
                "coverage_ratio": 0.0,
                "topic_evidence": {},
                "message": f"Validation error: {e}",
            }

    def validate_word_count(
        self, text: str, min_words: int = 800, max_words: int = 1500
    ) -> Dict[str, Any]:
        """
        Check if text length is appropriate.

        Returns:
            Dict with 'passed', 'word_count', 'min_words', 'max_words'
        """
        try:
            words = text.split()
            word_count = len(words)
            passed = min_words <= word_count <= max_words

            logger.info(
                "Word count validation",
                count=word_count,
                range=f"{min_words}-{max_words}",
                passed=passed,
            )

            return {
                "passed": passed,
                "word_count": word_count,
                "min_words": min_words,
                "max_words": max_words,
                "message": f"Word count: {word_count} (target: {min_words}-{max_words})",
            }

        except Exception as e:
            logger.error("Word count validation failed", error=str(e))
            return {
                "passed": False,
                "word_count": 0,
                "min_words": min_words,
                "max_words": max_words,
                "message": f"Validation error: {e}",
            }

    def validate_singapore_context(self, text: str) -> Dict[str, Any]:
        """
        Check if text mentions Singapore legal context.

        Returns:
            Dict with 'passed', 'singapore_mentions', 'evidence'
        """
        try:
            singapore_indicators = [
                "singapore",
                "singaporean",
                "s$",
                "sgd",
                "orchard",
                "raffles",
                "marina bay",
                "changi",
                "hdb",
                "condo",
                "condominium",
                "high court",
                "court of appeal",
                "supreme court",
            ]

            text_lower = text.lower()
            found_indicators = [
                ind for ind in singapore_indicators if ind in text_lower
            ]

            passed = len(found_indicators) > 0

            logger.info(
                "Singapore context validation",
                indicators_found=len(found_indicators),
                passed=passed,
            )

            return {
                "passed": passed,
                "singapore_mentions": len(found_indicators),
                "evidence": found_indicators,
                "message": f"Found {len(found_indicators)} Singapore context indicators",
            }

        except Exception as e:
            logger.error("Singapore context validation failed", error=str(e))
            return {
                "passed": False,
                "singapore_mentions": 0,
                "evidence": [],
                "message": f"Validation error: {e}",
            }

    def calculate_overall_score(
        self, validation_results: Dict[str, Dict[str, Any]]
    ) -> Tuple[float, bool]:
        """
        Calculate overall quality score from validation results.

        Args:
            validation_results: Dict mapping check name to check result

        Returns:
            Tuple of (score out of 10, passed boolean)
        """
        try:
            score = 0.0

            # Party count (2.5 points)
            if validation_results.get("party_count", {}).get("passed"):
                score += 2.5

            # Topic inclusion (4 points, scaled by coverage)
            topic_coverage = validation_results.get("topic_inclusion", {}).get(
                "coverage_ratio", 0.0
            )
            score += topic_coverage * 4.0

            # Word count (1.5 points)
            if validation_results.get("word_count", {}).get("passed"):
                score += 1.5

            # Singapore context (2 points)
            if validation_results.get("singapore_context", {}).get("passed"):
                score += 2.0

            # Pass if score >= 7.0 (70%)
            passed = score >= 7.0

            logger.info(
                "Overall validation score calculated",
                score=f"{score:.1f}/10",
                passed=passed,
            )

            return score, passed

        except Exception as e:
            logger.error("Score calculation failed", error=str(e))
            return 0.0, False

    def calculate_fast_score(
        self, validation_results: Dict[str, Dict[str, Any]]
    ) -> Tuple[float, bool]:
        """Calculate score for low-latency mode using topic+party checks only."""
        try:
            score = 0.0
            if validation_results.get("party_count", {}).get("passed"):
                score += 4.0
            topic_coverage = validation_results.get("topic_inclusion", {}).get(
                "coverage_ratio", 0.0
            )
            score += topic_coverage * 6.0
            passed = score >= 6.5
            logger.info(
                "Fast validation score calculated",
                score=f"{score:.1f}/10",
                passed=passed,
            )
            return score, passed
        except Exception as e:
            logger.error("Fast score calculation failed", error=str(e))
            return 0.0, False

    def validate_chronology_coherence(self, text: str) -> Dict[str, Any]:
        """Check whether timeline cues and explicit years form a plausible chronology."""
        try:
            text_lower = text.lower()
            issues: List[str] = []

            year_matches = [int(match) for match in re.findall(r"\b(19\d{2}|20\d{2})\b", text)]
            if len(year_matches) >= 2:
                if year_matches != sorted(year_matches):
                    issues.append("non_monotonic_year_order")
                if (max(year_matches) - min(year_matches)) > 30:
                    issues.append("excessive_year_span")

            if "before" in text_lower and "after" in text_lower:
                before_count = text_lower.count("before")
                after_count = text_lower.count("after")
                if abs(before_count - after_count) > 4:
                    issues.append("imbalanced_temporal_connectors")

            if "subsequently" in text_lower and "prior to" in text_lower:
                issues.append("mixed_temporal_direction_cues")

            coherence_score = max(0.0, 1.0 - (0.25 * len(issues)))
            passed = coherence_score >= 0.6
            return {
                "passed": passed,
                "coherence_score": round(coherence_score, 3),
                "issues": issues,
                "years": year_matches,
            }
        except Exception as e:
            logger.error("Chronology coherence validation failed", error=str(e))
            return {
                "passed": False,
                "coherence_score": 0.0,
                "issues": ["chronology_validation_error"],
                "error": str(e),
            }

    def validate_party_role_clarity(self, text: str) -> Dict[str, Any]:
        """Check whether party roles are explicit enough for exam-style issue analysis."""
        try:
            text_lower = text.lower()
            claimant_terms = [
                "plaintiff",
                "claimant",
                "applicant",
                "injured party",
            ]
            defendant_terms = [
                "defendant",
                "respondent",
                "alleged tortfeasor",
                "liable party",
            ]
            role_context_terms = [
                "employer",
                "employee",
                "driver",
                "pedestrian",
                "occupier",
                "visitor",
            ]

            claimant_hits = [term for term in claimant_terms if term in text_lower]
            defendant_hits = [term for term in defendant_terms if term in text_lower]
            role_context_hits = [term for term in role_context_terms if term in text_lower]
            named_party_tokens = re.findall(r"\b[A-Z][a-z]{2,}\b", text)

            role_pair_present = bool(claimant_hits and defendant_hits)
            named_party_count = len(set(named_party_tokens))
            clarity_score = (
                (0.45 if claimant_hits else 0.0)
                + (0.45 if defendant_hits else 0.0)
                + (0.1 if role_context_hits else 0.0)
            )
            if named_party_count >= 2:
                clarity_score = min(1.0, clarity_score + 0.1)
            clarity_score = round(clarity_score, 3)

            return {
                "passed": role_pair_present and clarity_score >= 0.6,
                "clarity_score": clarity_score,
                "role_pair_present": role_pair_present,
                "named_party_count": named_party_count,
                "evidence": {
                    "claimant_terms": claimant_hits,
                    "defendant_terms": defendant_hits,
                    "role_context_terms": role_context_hits,
                },
            }
        except Exception as e:
            logger.error("Party-role clarity validation failed", error=str(e))
            return {
                "passed": False,
                "clarity_score": 0.0,
                "role_pair_present": False,
                "named_party_count": 0,
                "evidence": {},
                "error": str(e),
            }

    def validate_legal_realism(self, text: str) -> Dict[str, Any]:
        """Score legal realism signals: SG venue cues, procedure cues, and timeline coherence."""
        try:
            text_lower = text.lower()
            singapore_context_cues = [
                "singapore",
                "state courts",
                "high court",
                "district court",
                "subordinate courts",
                "attorney-general",
                "singapore law reports",
                "rules of court",
                "hdb",
                "mrt",
                "lta",
                "mom",
                "cpf",
                "orchard road",
                "jurong",
                "tampines",
            ]
            procedure_cues = [
                "plaintiff",
                "defendant",
                "claim",
                "liability",
                "damages",
                "defence",
                "breach",
                "duty",
                "causation",
            ]
            timeline_cues = [
                "on",
                "before",
                "after",
                "later",
                "subsequently",
                "then",
                "months",
                "years",
            ]

            found_singapore_context = [
                cue for cue in singapore_context_cues if cue in text_lower
            ]
            found_procedure = [cue for cue in procedure_cues if cue in text_lower]
            found_timeline = [cue for cue in timeline_cues if cue in text_lower]
            chronology_result = self.validate_chronology_coherence(text)
            party_role_result = self.validate_party_role_clarity(text)

            singapore_context_score = min(1.0, len(found_singapore_context) / 4.0)
            procedure_score = min(1.0, len(found_procedure) / 4.0)
            timeline_score = min(1.0, len(found_timeline) / 3.0)
            chronology_score = float(chronology_result.get("coherence_score", 0.0))
            party_role_score = float(party_role_result.get("clarity_score", 0.0))
            realism_score = round(
                (singapore_context_score * 0.32)
                + (procedure_score * 0.23)
                + (timeline_score * 0.1)
                + (chronology_score * 0.2)
                + (party_role_score * 0.15),
                3,
            )
            passed = realism_score >= 0.6

            return {
                "passed": passed,
                "realism_score": realism_score,
                "components": {
                    "singapore_context_score": round(singapore_context_score, 3),
                    "procedure_score": round(procedure_score, 3),
                    "timeline_score": round(timeline_score, 3),
                    "chronology_score": round(chronology_score, 3),
                    "party_role_score": round(party_role_score, 3),
                },
                "evidence": {
                    "singapore_context": found_singapore_context,
                    "procedure": found_procedure,
                    "timeline": found_timeline,
                    "chronology": chronology_result,
                    "party_roles": party_role_result,
                },
            }
        except Exception as e:
            logger.error("Legal realism validation failed", error=str(e))
            return {
                "passed": False,
                "realism_score": 0.0,
                "components": {},
                "evidence": {},
                "error": str(e),
            }

    def validate_exam_likeness(self, text: str) -> Dict[str, Any]:
        """Score exam-likeness signals: issue density, ambiguity balance, fact sufficiency."""
        try:
            text_lower = text.lower()
            issue_terms = [
                "issue",
                "duty",
                "breach",
                "causation",
                "remoteness",
                "defence",
                "liability",
                "damages",
            ]
            ambiguity_terms = [
                "unclear",
                "disputed",
                "arguably",
                "may",
                "might",
                "however",
                "alternatively",
            ]
            fact_terms = [
                "date",
                "time",
                "location",
                "injury",
                "contract",
                "statement",
                "witness",
                "evidence",
            ]

            issue_hits = [term for term in issue_terms if term in text_lower]
            ambiguity_hits = [term for term in ambiguity_terms if term in text_lower]
            fact_hits = [term for term in fact_terms if term in text_lower]

            issue_density = min(1.0, len(issue_hits) / 5.0)
            # Ambiguity should not be too low or too high; centered around 3 hits.
            ambiguity_count = len(ambiguity_hits)
            ambiguity_balance = max(0.0, 1.0 - (abs(ambiguity_count - 3) / 3.0))
            fact_sufficiency = min(1.0, len(fact_hits) / 4.0)

            exam_score = round(
                (issue_density * 0.45)
                + (ambiguity_balance * 0.25)
                + (fact_sufficiency * 0.30),
                3,
            )
            passed = exam_score >= 0.6

            return {
                "passed": passed,
                "exam_likeness_score": exam_score,
                "components": {
                    "issue_density": round(issue_density, 3),
                    "ambiguity_balance": round(ambiguity_balance, 3),
                    "fact_sufficiency": round(fact_sufficiency, 3),
                },
                "evidence": {
                    "issues": issue_hits,
                    "ambiguity": ambiguity_hits,
                    "facts": fact_hits,
                },
            }
        except Exception as e:
            logger.error("Exam-likeness validation failed", error=str(e))
            return {
                "passed": False,
                "exam_likeness_score": 0.0,
                "components": {},
                "evidence": {},
                "error": str(e),
            }

    def _get_ml_pipeline(self):
        """Lazy-load ML pipeline for enhanced validation."""
        if not hasattr(self, "_ml_pipeline"):
            self._ml_pipeline = None
            try:
                from ..ml.pipeline import MLPipeline

                self._ml_pipeline = MLPipeline()
                self._ml_pipeline.load_all()
            except Exception:
                pass
        return self._ml_pipeline

    def validate_hypothetical(
        self,
        text: str,
        required_topics: List[str],
        expected_parties: int,
        law_domain: str = "tort",
        fast_mode: bool = False,
    ) -> Dict[str, Any]:
        """
        Run all validation checks on a hypothetical.

        Returns:
            Complete validation result with all checks
        """
        try:
            # Run all validation checks
            party_result = self.validate_party_count(text, expected_parties)
            topic_result = self.validate_topic_inclusion(text, required_topics)

            if fast_mode:
                fast_results = {
                    "party_count": party_result,
                    "topic_inclusion": topic_result,
                }
                overall_score, passed = self.calculate_fast_score(fast_results)
                return {
                    "passed": passed,
                    "overall_score": overall_score,
                    "checks": fast_results,
                    "summary": {
                        "mode": "fast",
                        "parties": f"{party_result['actual_count']}/{expected_parties}",
                        "topics": f"{len(topic_result['topics_found'])}/{len(required_topics)}",
                    },
                }

            word_result = self.validate_word_count(text)
            singapore_result = self.validate_singapore_context(text)
            legal_realism_result = self.validate_legal_realism(text)
            exam_likeness_result = self.validate_exam_likeness(text)

            # Collect all results
            all_results = {
                "party_count": party_result,
                "topic_inclusion": topic_result,
                "word_count": word_result,
                "singapore_context": singapore_result,
                "legal_realism": legal_realism_result,
                "exam_likeness": exam_likeness_result,
            }

            # Calculate overall score
            overall_score, passed = self.calculate_overall_score(all_results)

            # ML-enhanced checks (non-blocking)
            ml_checks = self._run_ml_checks(text, required_topics)
            if ml_checks:
                all_results["ml_topic_check"] = ml_checks.get("ml_topic_check", {})
                all_results["ml_quality_check"] = ml_checks.get("ml_quality_check", {})

            return {
                "passed": passed,
                "overall_score": overall_score,
                "checks": all_results,
                "summary": {
                    "parties": f"{party_result['actual_count']}/{expected_parties}",
                    "topics": f"{len(topic_result['topics_found'])}/{len(required_topics)}",
                    "words": word_result["word_count"],
                    "singapore_context": singapore_result["passed"],
                    "legal_realism": legal_realism_result["realism_score"],
                    "exam_likeness": exam_likeness_result["exam_likeness_score"],
                },
            }

        except Exception as e:
            logger.error("Hypothetical validation failed", error=str(e))
            return {
                "passed": False,
                "overall_score": 0.0,
                "checks": {},
                "summary": {},
                "error": str(e),
            }

    def _run_ml_checks(self, text: str, required_topics: List[str]) -> Dict:
        """Run ML-based validation checks if models are trained."""
        pipeline = self._get_ml_pipeline()
        if not pipeline:
            return {}
        result = {}
        try:
            prediction = pipeline.predict(text)
            if "topics" in prediction:
                ml_topics = set(prediction["topics"])
                req_topics = set(required_topics)
                match = bool(ml_topics & req_topics) if ml_topics else True
                result["ml_topic_check"] = {
                    "passed": match,
                    "ml_predicted_topics": list(ml_topics),
                    "requested_topics": required_topics,
                    "message": f"ML predicted {list(ml_topics)}, requested {required_topics}",
                }
            if "quality" in prediction:
                result["ml_quality_check"] = {
                    "ml_quality_score": prediction["quality"],
                    "message": f"ML predicted quality: {prediction['quality']:.2f}",
                }
        except Exception as e:
            logger.warning("ML checks failed (non-fatal)", error=str(e))
        return result


# Global validation service instance
validation_service = ValidationService()
