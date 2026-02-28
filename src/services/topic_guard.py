"""Topic validation helpers shared by API generation endpoints."""

from typing import List

from fastapi import HTTPException, status

from ..domain import canonicalize_topic, is_tort_topic


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
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Invalid non-tort topics: "
                f"{invalid_topics}. Allowed domain topics are tort topics only."
            ),
        )
    return canonical_topics
