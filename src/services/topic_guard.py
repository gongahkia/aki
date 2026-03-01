"""Topic validation helpers shared by API generation endpoints."""

from typing import List

from ..domain import canonicalize_topic, is_tort_topic


class TopicValidationError(ValueError):
    """Raised when one or more topics fall outside the supported tort domain."""


def canonicalize_and_validate_topics(topics: List[str]) -> List[str]:
    """Canonicalize topics and enforce tort-topic registry membership."""
    canonical_topics: List[str] = []
    invalid_topics: List[str] = []
    for topic in topics:
        canonical = canonicalize_topic(topic)
        if not is_tort_topic(canonical):
            invalid_topics.append(topic)
            continue
        canonical_topics.append(canonical)

    if invalid_topics:
        raise TopicValidationError(
            "Invalid non-tort topics: "
            f"{invalid_topics}. Allowed domain topics are tort topics only."
        )
    return canonical_topics
