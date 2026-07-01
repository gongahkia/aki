"""Domain-pack registry for jurisdiction-specific legal modules."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Tuple

from .topics import (
    TOPIC_ALIASES,
    TopicDefinition,
    all_tort_topic_keys,
    normalize_topic_token,
)


def normalize_scope_token(value: str) -> str:
    normalized = (value or "").strip().lower()
    normalized = normalized.replace("-", " ")
    normalized = " ".join(normalized.split())
    return normalized.replace(" ", "_")


@dataclass(frozen=True)
class Jurisdiction:
    """First-class jurisdiction metadata for corpus routing."""

    key: str
    display_name: str
    legal_system: str = "common_law"
    aliases: Tuple[str, ...] = ()

    def matches(self, value: str) -> bool:
        token = normalize_scope_token(value)
        accepted = {
            normalize_scope_token(self.key),
            normalize_scope_token(self.display_name),
        }
        accepted.update(normalize_scope_token(alias) for alias in self.aliases)
        return token in accepted


@dataclass(frozen=True)
class DomainPack:
    """Describes a pluggable legal-domain package."""

    key: str
    display_name: str
    jurisdiction: Jurisdiction
    law_domain: str
    canonicalize_topic: Callable[[str], str]
    is_supported_topic: Callable[[str], bool]
    topic_keys: Tuple[str, ...]
    topic_aliases: Mapping[str, str]
    subject_label: str = "Tort Law"
    topic_definitions: Mapping[str, TopicDefinition] | None = None
    prompt_overlay: Mapping[str, Any] | None = None
    validation_overlay: Mapping[str, Any] | None = None
    manifest_path: str = ""
    corpus_path: str = ""
    raw_paths: Tuple[str, ...] = ()
    record_format: str = ""

    @property
    def jurisdiction_key(self) -> str:
        return self.jurisdiction.key

    @property
    def subject_key(self) -> str:
        return self.law_domain


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_manifest(path: str) -> Dict[str, Any]:
    manifest_path = _repo_root() / path
    try:
        with manifest_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _manifest_mapping(key: str) -> Dict[str, Any]:
    value = _SG_TORT_MANIFEST.get(key, {})
    return value if isinstance(value, dict) else {}


def _build_topic_definitions(taxonomy: Mapping[str, Any]) -> Dict[str, TopicDefinition]:
    topics = taxonomy.get("topics", [])
    definitions: Dict[str, TopicDefinition] = {}
    if not isinstance(topics, list):
        return definitions
    for item in topics:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key", "")).strip()
        if not key:
            continue
        aliases = item.get("aliases", [])
        alias_values = tuple(str(alias) for alias in aliases if str(alias).strip())
        definitions[key] = TopicDefinition(
            key=key,
            label=str(item.get("label", key.replace("_", " ").title())),
            category=str(item.get("category", "")),
            description=str(item.get("description", "")),
            aliases=alias_values,
        )
    return definitions


def _build_topic_aliases(
    definitions: Mapping[str, TopicDefinition],
) -> Dict[str, str]:
    aliases: Dict[str, str] = {}
    for definition in definitions.values():
        tokens = [definition.key, definition.key.replace("_", " ")]
        tokens.extend(definition.aliases)
        for token in tokens:
            aliases[normalize_topic_token(token)] = definition.key
    return aliases


def _canonicalize_from_aliases(topic: str, aliases: Mapping[str, str]) -> str:
    token = normalize_topic_token(topic)
    return aliases.get(token, token)


_SG_TORT_MANIFEST_PATH = "corpus/packs/sg_tort/manifest.json"
_SG_TORT_MANIFEST = _load_manifest(_SG_TORT_MANIFEST_PATH)
_SG_TORT_CORPUS = _manifest_mapping("corpus")
_SG_TORT_TAXONOMY = _manifest_mapping("taxonomy")
_SG_TORT_TOPIC_DEFINITIONS = _build_topic_definitions(_SG_TORT_TAXONOMY)
if not _SG_TORT_TOPIC_DEFINITIONS:
    _SG_TORT_TOPIC_DEFINITIONS = {
        key: TopicDefinition(
            key=key,
            label=key.replace("_", " ").title(),
            category="",
            description="",
        )
        for key in all_tort_topic_keys()
    }
_SG_TORT_TOPIC_ALIASES = _build_topic_aliases(_SG_TORT_TOPIC_DEFINITIONS)
if not _SG_TORT_TOPIC_ALIASES:
    _SG_TORT_TOPIC_ALIASES = dict(TOPIC_ALIASES)
_SG_TORT_OVERLAYS = _manifest_mapping("overlays")
_SG_TORT_PROMPT_OVERLAY = _SG_TORT_OVERLAYS.get("prompt", {})
if not isinstance(_SG_TORT_PROMPT_OVERLAY, dict):
    _SG_TORT_PROMPT_OVERLAY = {}
_SG_TORT_VALIDATION_OVERLAY = _SG_TORT_OVERLAYS.get("validation", {})
if not isinstance(_SG_TORT_VALIDATION_OVERLAY, dict):
    _SG_TORT_VALIDATION_OVERLAY = {}


DOMAIN_PACK_REGISTRY: Dict[str, DomainPack] = {
    "sg_tort": DomainPack(
        key="sg_tort",
        display_name="Singapore Tort Law",
        jurisdiction=Jurisdiction(
            key="sg",
            display_name="Singapore",
            aliases=("singapore_law", "singapore tort", "singapore_tort"),
        ),
        law_domain="tort",
        canonicalize_topic=lambda topic: _canonicalize_from_aliases(
            topic, _SG_TORT_TOPIC_ALIASES
        ),
        is_supported_topic=lambda topic: _canonicalize_from_aliases(
            topic, _SG_TORT_TOPIC_ALIASES
        )
        in _SG_TORT_TOPIC_DEFINITIONS,
        topic_keys=tuple(_SG_TORT_TOPIC_DEFINITIONS.keys()),
        topic_aliases=dict(_SG_TORT_TOPIC_ALIASES),
        manifest_path=_SG_TORT_MANIFEST_PATH,
        topic_definitions=dict(_SG_TORT_TOPIC_DEFINITIONS),
        prompt_overlay=dict(_SG_TORT_PROMPT_OVERLAY),
        validation_overlay=dict(_SG_TORT_VALIDATION_OVERLAY),
        corpus_path=str(
            _SG_TORT_CORPUS.get("clean_path", "corpus/clean/tort/corpus.json")
        ),
        raw_paths=tuple(_SG_TORT_CORPUS.get("raw_paths", ("corpus/raw/tort",))),
        record_format=str(_SG_TORT_CORPUS.get("record_format", "legacy_text_topic_v1")),
    )
}


def register_domain_pack(domain_pack: DomainPack) -> None:
    """Register or replace a domain pack by key."""
    DOMAIN_PACK_REGISTRY[domain_pack.key] = domain_pack


def get_domain_pack(key: str = "sg_tort") -> DomainPack:
    """Fetch a domain pack by key."""
    if key not in DOMAIN_PACK_REGISTRY:
        raise KeyError(f"Unknown domain pack '{key}'")
    return DOMAIN_PACK_REGISTRY[key]


def list_domain_packs() -> Tuple[DomainPack, ...]:
    """List all registered domain packs."""
    return tuple(DOMAIN_PACK_REGISTRY.values())


def default_domain_pack() -> DomainPack:
    """Return the default domain pack used by current services."""
    return get_domain_pack("sg_tort")


def resolve_domain_pack(key: str | None = None) -> DomainPack:
    """Fetch requested pack or default to SG Tort."""
    return get_domain_pack((key or "sg_tort").strip() or "sg_tort")
