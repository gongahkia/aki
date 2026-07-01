"""Topic validation helpers shared by API generation endpoints."""

from typing import List

from ..domain import resolve_domain_pack


class TopicValidationError(ValueError):
    """Raised when one or more topics fall outside the selected domain pack."""


def canonicalize_and_validate_topics(
    topics: List[str], *, corpus_pack: str = "sg_tort"
) -> List[str]:
    """Canonicalize topics and enforce the selected pack registry."""
    domain_pack = resolve_domain_pack(corpus_pack)
    canonical_topics: List[str] = []
    invalid_topics: List[str] = []
    for topic in topics:
        canonical = domain_pack.canonicalize_topic(topic)
        if not domain_pack.is_supported_topic(canonical):
            invalid_topics.append(topic)
            continue
        canonical_topics.append(canonical)

    if invalid_topics:
        raise TopicValidationError(
            f"Invalid topics for {domain_pack.key}: {invalid_topics}. "
            f"Allowed topics are defined by {domain_pack.display_name}."
        )
    return canonical_topics
