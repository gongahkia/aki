"""Canonical tort-topic registry and normalization helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Tuple


@dataclass(frozen=True)
class TopicDefinition:
    """Immutable metadata for a canonical tort topic."""

    key: str
    label: str
    category: str
    description: str
    aliases: Tuple[str, ...] = ()


TORT_TOPICS: Dict[str, TopicDefinition] = {
    "negligence": TopicDefinition(
        key="negligence",
        label="Negligence",
        category="Negligence-Based",
        description="duty, breach, damage, causation",
    ),
    "duty_of_care": TopicDefinition(
        key="duty_of_care",
        label="Duty Of Care",
        category="Negligence-Based",
        description="neighbour principle, proximity",
        aliases=("duty of care",),
    ),
    "standard_of_care": TopicDefinition(
        key="standard_of_care",
        label="Standard Of Care",
        category="Negligence-Based",
        description="reasonable person standard",
        aliases=("standard of care",),
    ),
    "causation": TopicDefinition(
        key="causation",
        label="Causation",
        category="Negligence-Based",
        description="but-for test, legal causation",
    ),
    "remoteness": TopicDefinition(
        key="remoteness",
        label="Remoteness",
        category="Negligence-Based",
        description="foreseeability of damage",
    ),
    "contributory_negligence": TopicDefinition(
        key="contributory_negligence",
        label="Contributory Negligence",
        category="Negligence-Based",
        description="claimant's own fault",
        aliases=("contributory negligence",),
    ),
    "battery": TopicDefinition(
        key="battery",
        label="Battery",
        category="Intentional Torts",
        description="intentional application of force",
    ),
    "assault": TopicDefinition(
        key="assault",
        label="Assault",
        category="Intentional Torts",
        description="apprehension of immediate contact",
    ),
    "false_imprisonment": TopicDefinition(
        key="false_imprisonment",
        label="False Imprisonment",
        category="Intentional Torts",
        description="unlawful restraint of liberty",
        aliases=("false imprisonment",),
    ),
    "trespass_to_land": TopicDefinition(
        key="trespass_to_land",
        label="Trespass To Land",
        category="Intentional Torts",
        description="unlawful entry onto land",
        aliases=("trespass to land",),
    ),
    "vicarious_liability": TopicDefinition(
        key="vicarious_liability",
        label="Vicarious Liability",
        category="Liability",
        description="employer liability for employee torts",
        aliases=("vicarious liability",),
    ),
    "strict_liability": TopicDefinition(
        key="strict_liability",
        label="Strict Liability",
        category="Liability",
        description="liability without fault",
        aliases=("strict liability",),
    ),
    "occupiers_liability": TopicDefinition(
        key="occupiers_liability",
        label="Occupiers Liability",
        category="Liability",
        description="duties to visitors and trespassers",
        aliases=("occupiers liability",),
    ),
    "employers_liability": TopicDefinition(
        key="employers_liability",
        label="Employers Liability",
        category="Liability",
        description="workplace safety duties",
        aliases=("employers liability",),
    ),
    "product_liability": TopicDefinition(
        key="product_liability",
        label="Product Liability",
        category="Liability",
        description="defective product claims",
        aliases=("product liability",),
    ),
    "defamation": TopicDefinition(
        key="defamation",
        label="Defamation",
        category="Specific Torts",
        description="false statements harming reputation",
    ),
    "private_nuisance": TopicDefinition(
        key="private_nuisance",
        label="Private Nuisance",
        category="Specific Torts",
        description="unreasonable interference with land use",
        aliases=("private nuisance",),
    ),
    "harassment": TopicDefinition(
        key="harassment",
        label="Harassment",
        category="Specific Torts",
        description="course of conduct causing alarm",
    ),
    "economic_loss": TopicDefinition(
        key="economic_loss",
        label="Economic Loss",
        category="Damages",
        description="pure financial loss claims",
        aliases=("economic loss",),
    ),
    "psychiatric_harm": TopicDefinition(
        key="psychiatric_harm",
        label="Psychiatric Harm",
        category="Damages",
        description="nervous shock and mental injury",
        aliases=("psychiatric harm",),
    ),
    "breach_of_statutory_duty": TopicDefinition(
        key="breach_of_statutory_duty",
        label="Breach Of Statutory Duty",
        category="Doctrines & Defences",
        description="breach of obligations imposed by statute",
        aliases=("breach of statutory duty",),
    ),
    "rylands_v_fletcher": TopicDefinition(
        key="rylands_v_fletcher",
        label="Rylands V Fletcher",
        category="Doctrines & Defences",
        description="strict liability for escape of dangerous things",
        aliases=("rylands v fletcher",),
    ),
    "consent_defence": TopicDefinition(
        key="consent_defence",
        label="Consent Defence",
        category="Doctrines & Defences",
        description="voluntary assumption of known risk",
        aliases=("consent defence",),
    ),
    "illegality_defence": TopicDefinition(
        key="illegality_defence",
        label="Illegality Defence",
        category="Doctrines & Defences",
        description="claim barred by claimant illegality",
        aliases=("illegality defence",),
    ),
    "limitation_periods": TopicDefinition(
        key="limitation_periods",
        label="Limitation Periods",
        category="Doctrines & Defences",
        description="time-bar and accrual limits",
        aliases=("limitation periods",),
    ),
    "res_ipsa_loquitur": TopicDefinition(
        key="res_ipsa_loquitur",
        label="Res Ipsa Loquitur",
        category="Doctrines & Defences",
        description="inference of negligence from circumstances",
        aliases=("res ipsa loquitur",),
    ),
    "novus_actus_interveniens": TopicDefinition(
        key="novus_actus_interveniens",
        label="Novus Actus Interveniens",
        category="Doctrines & Defences",
        description="intervening act breaks causation chain",
        aliases=("novus actus interveniens",),
    ),
    "volenti_non_fit_injuria": TopicDefinition(
        key="volenti_non_fit_injuria",
        label="Volenti Non Fit Injuria",
        category="Doctrines & Defences",
        description="no injury where risk was voluntarily accepted",
        aliases=("volenti non fit injuria",),
    ),
}


def normalize_topic_token(topic: str) -> str:
    """Normalize input topic into a comparable snake_case token."""
    normalized = (topic or "").strip().lower()
    normalized = normalized.replace("-", " ")
    normalized = " ".join(normalized.split())
    return normalized.replace(" ", "_")


def _iter_lookup_tokens(topic_def: TopicDefinition) -> Iterable[str]:
    yield topic_def.key
    yield topic_def.key.replace("_", " ")
    for alias in topic_def.aliases:
        yield alias


TOPIC_ALIASES: Dict[str, str] = {}
for definition in TORT_TOPICS.values():
    for token in _iter_lookup_tokens(definition):
        TOPIC_ALIASES[normalize_topic_token(token)] = definition.key


def canonicalize_topic(topic: str, *, strict: bool = False) -> str:
    """Resolve a topic alias to its canonical tort key."""
    token = normalize_topic_token(topic)
    canonical = TOPIC_ALIASES.get(token)
    if canonical:
        return canonical
    if strict:
        raise ValueError(f"Unknown tort topic: {topic}")
    return token


def is_tort_topic(topic: str) -> bool:
    """Return True when the topic resolves to a canonical tort key."""
    return canonicalize_topic(topic) in TORT_TOPICS


def all_tort_topic_keys() -> Tuple[str, ...]:
    """Return all canonical tort topic keys in registry order."""
    return tuple(TORT_TOPICS.keys())
