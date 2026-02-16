"""
Validation Service for deterministic hypothetical validation.
Replaces expensive LLM-based validation with fast, reliable programmatic checks.
"""

import re
from typing import Dict, List, Any, Tuple
from collections import Counter
import structlog

logger = structlog.get_logger(__name__)


class ValidationService:
    """Service for deterministic validation of legal hypotheticals."""

    def __init__(self):
        # Common person/entity indicators
        self._person_indicators = [
            r'\b[A-Z][a-z]+\s+[A-Z][a-z]+\b',  # First Last name
            r'\b(?:Mr|Mrs|Ms|Dr|Prof)\.?\s+[A-Z][a-z]+',  # Titled names
            r'\b[A-Z][a-z]+\b(?:\s+(?:Pte|Ltd|Inc|Corp|LLC|LLP))',  # Companies
        ]

        # Singapore tort law keywords by topic
        self._topic_keywords = {
            'negligence': ['negligent', 'negligence', 'duty', 'breach', 'reasonable person', 'standard of care'],
            'duty of care': ['duty of care', 'duty', 'owed', 'responsibility', 'obligation'],
            'standard of care': ['standard', 'reasonable', 'prudent', 'expected'],
            'causation': ['causation', 'caused', 'resulting', 'consequence', 'led to'],
            'remoteness': ['remote', 'foreseeable', 'foreseeability', 'proximate'],
            'battery': ['battery', 'intentional', 'contact', 'touching', 'physical force'],
            'assault': ['assault', 'threat', 'fear', 'apprehension', 'imminent'],
            'false imprisonment': ['imprisonment', 'confined', 'restrained', 'detained', 'liberty'],
            'defamation': ['defamation', 'defamatory', 'reputation', 'slander', 'libel'],
            'private nuisance': ['nuisance', 'interference', 'enjoyment', 'land', 'property'],
            'trespass to land': ['trespass', 'entered', 'land', 'property', 'without permission'],
            'vicarious liability': ['vicarious', 'employer', 'employee', 'course of employment'],
            'strict liability': ['strict liability', 'no fault', 'absolute', 'inherently dangerous'],
            'harassment': ['harassment', 'harass', 'alarm', 'distress'],
            'occupiers_liability': ['occupier', 'visitor', 'premises', 'invitee', 'licensee', 'trespasser'],
            'product_liability': ['manufacturer', 'product', 'defect', 'consumer', 'safety'],
            'contributory_negligence': ['contributory', 'claimant', 'own fault', 'contributed', 'apportionment'],
            'economic_loss': ['economic loss', 'pure economic', 'financial loss', 'pecuniary'],
            'psychiatric_harm': ['psychiatric', 'nervous shock', 'mental injury', 'ptsd', 'psychological'],
            'employers_liability': ['employer', 'workplace', 'occupational', 'safe system', 'employee injury'],
            'breach_of_statutory_duty': ['statutory duty', 'statute', 'breach of duty', 'legislative', 'regulation'],
            'rylands_v_fletcher': ['rylands', 'fletcher', 'escape', 'non-natural use', 'accumulation'],
            'consent_defence': ['consent', 'volenti', 'agreed', 'assumption of risk', 'willing'],
            'illegality_defence': ['illegality', 'ex turpi', 'illegal act', 'unlawful', 'criminal'],
            'limitation_periods': ['limitation', 'time bar', 'statute of limitations', 'accrual', 'prescribed period'],
            'res_ipsa_loquitur': ['res ipsa', 'speaks for itself', 'inference', 'control', 'without explanation'],
            'novus_actus_interveniens': ['novus actus', 'intervening', 'break in chain', 'superseding cause', 'new act'],
            'volenti_non_fit_injuria': ['volenti', 'voluntary assumption', 'consent to risk', 'willing participant'],
        }

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
            common_words = {'Singapore', 'Tort', 'Law', 'Court', 'The', 'A', 'An'}
            entities = {e for e in entities if not any(word in e for word in common_words)}

            actual_count = len(entities)
            passed = actual_count >= expected_count  # Allow more parties than requested

            logger.info("Party count validation",
                       expected=expected_count,
                       actual=actual_count,
                       passed=passed)

            return {
                'passed': passed,
                'expected_count': expected_count,
                'actual_count': actual_count,
                'entities': list(entities),
                'message': f"Found {actual_count} parties (expected {expected_count})"
            }

        except Exception as e:
            logger.error("Party count validation failed", error=str(e))
            return {
                'passed': False,
                'expected_count': expected_count,
                'actual_count': 0,
                'entities': [],
                'message': f"Validation error: {e}"
            }

    def validate_topic_inclusion(self, text: str, required_topics: List[str]) -> Dict[str, Any]:
        """
        Check if required topics are present in text using keyword matching.

        Returns:
            Dict with 'passed', 'topics_found', 'topics_missing', 'coverage_ratio'
        """
        try:
            text_lower = text.lower()
            topics_found = []
            topic_evidence = {}

            for topic in required_topics:
                # Get keywords for this topic
                keywords = self._topic_keywords.get(topic.lower(), [topic.lower()])

                # Check if any keyword appears in text
                found_keywords = [kw for kw in keywords if kw.lower() in text_lower]

                if found_keywords:
                    topics_found.append(topic)
                    topic_evidence[topic] = found_keywords

            topics_missing = [t for t in required_topics if t not in topics_found]
            coverage_ratio = len(topics_found) / len(required_topics) if required_topics else 1.0

            # Pass if at least 70% of topics are covered
            passed = coverage_ratio >= 0.7

            logger.info("Topic inclusion validation",
                       required=len(required_topics),
                       found=len(topics_found),
                       coverage=f"{coverage_ratio:.1%}",
                       passed=passed)

            return {
                'passed': passed,
                'topics_found': topics_found,
                'topics_missing': topics_missing,
                'coverage_ratio': coverage_ratio,
                'topic_evidence': topic_evidence,
                'message': f"Found {len(topics_found)}/{len(required_topics)} topics ({coverage_ratio:.0%} coverage)"
            }

        except Exception as e:
            logger.error("Topic inclusion validation failed", error=str(e))
            return {
                'passed': False,
                'topics_found': [],
                'topics_missing': required_topics,
                'coverage_ratio': 0.0,
                'topic_evidence': {},
                'message': f"Validation error: {e}"
            }

    def validate_word_count(self, text: str, min_words: int = 800, max_words: int = 1500) -> Dict[str, Any]:
        """
        Check if text length is appropriate.

        Returns:
            Dict with 'passed', 'word_count', 'min_words', 'max_words'
        """
        try:
            words = text.split()
            word_count = len(words)
            passed = min_words <= word_count <= max_words

            logger.info("Word count validation",
                       count=word_count,
                       range=f"{min_words}-{max_words}",
                       passed=passed)

            return {
                'passed': passed,
                'word_count': word_count,
                'min_words': min_words,
                'max_words': max_words,
                'message': f"Word count: {word_count} (target: {min_words}-{max_words})"
            }

        except Exception as e:
            logger.error("Word count validation failed", error=str(e))
            return {
                'passed': False,
                'word_count': 0,
                'min_words': min_words,
                'max_words': max_words,
                'message': f"Validation error: {e}"
            }

    def validate_singapore_context(self, text: str) -> Dict[str, Any]:
        """
        Check if text mentions Singapore legal context.

        Returns:
            Dict with 'passed', 'singapore_mentions', 'evidence'
        """
        try:
            singapore_indicators = [
                'singapore', 'singaporean', 's$', 'sgd',
                'orchard', 'raffles', 'marina bay', 'changi',
                'hdb', 'condo', 'condominium',
                'high court', 'court of appeal', 'supreme court'
            ]

            text_lower = text.lower()
            found_indicators = [ind for ind in singapore_indicators if ind in text_lower]

            passed = len(found_indicators) > 0

            logger.info("Singapore context validation",
                       indicators_found=len(found_indicators),
                       passed=passed)

            return {
                'passed': passed,
                'singapore_mentions': len(found_indicators),
                'evidence': found_indicators,
                'message': f"Found {len(found_indicators)} Singapore context indicators"
            }

        except Exception as e:
            logger.error("Singapore context validation failed", error=str(e))
            return {
                'passed': False,
                'singapore_mentions': 0,
                'evidence': [],
                'message': f"Validation error: {e}"
            }

    def calculate_overall_score(self, validation_results: Dict[str, Dict[str, Any]]) -> Tuple[float, bool]:
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
            if validation_results.get('party_count', {}).get('passed'):
                score += 2.5

            # Topic inclusion (4 points, scaled by coverage)
            topic_coverage = validation_results.get('topic_inclusion', {}).get('coverage_ratio', 0.0)
            score += topic_coverage * 4.0

            # Word count (1.5 points)
            if validation_results.get('word_count', {}).get('passed'):
                score += 1.5

            # Singapore context (2 points)
            if validation_results.get('singapore_context', {}).get('passed'):
                score += 2.0

            # Pass if score >= 7.0 (70%)
            passed = score >= 7.0

            logger.info("Overall validation score calculated",
                       score=f"{score:.1f}/10",
                       passed=passed)

            return score, passed

        except Exception as e:
            logger.error("Score calculation failed", error=str(e))
            return 0.0, False

    def validate_hypothetical(
        self,
        text: str,
        required_topics: List[str],
        expected_parties: int,
        law_domain: str = "tort"
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
            word_result = self.validate_word_count(text)
            singapore_result = self.validate_singapore_context(text)

            # Collect all results
            all_results = {
                'party_count': party_result,
                'topic_inclusion': topic_result,
                'word_count': word_result,
                'singapore_context': singapore_result
            }

            # Calculate overall score
            overall_score, passed = self.calculate_overall_score(all_results)

            return {
                'passed': passed,
                'overall_score': overall_score,
                'checks': all_results,
                'summary': {
                    'parties': f"{party_result['actual_count']}/{expected_parties}",
                    'topics': f"{len(topic_result['topics_found'])}/{len(required_topics)}",
                    'words': word_result['word_count'],
                    'singapore_context': singapore_result['passed']
                }
            }

        except Exception as e:
            logger.error("Hypothetical validation failed", error=str(e))
            return {
                'passed': False,
                'overall_score': 0.0,
                'checks': {},
                'summary': {},
                'error': str(e)
            }


# Global validation service instance
validation_service = ValidationService()
