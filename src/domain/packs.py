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
    supplemental_corpus_paths: Tuple[str, ...] = ()
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


def _manifest_mapping(manifest: Mapping[str, Any], key: str) -> Dict[str, Any]:
    value = manifest.get(key, {})
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


def _string_tuple(value: Any) -> Tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(str(item) for item in value if str(item).strip())


def _overlay_mapping(overlays: Mapping[str, Any], key: str) -> Dict[str, Any]:
    value = overlays.get(key, {})
    return value if isinstance(value, dict) else {}


def _domain_pack_from_manifest(
    manifest_path: str,
    *,
    fallback_clean_path: str,
    fallback_raw_paths: Tuple[str, ...],
    fallback_record_format: str,
    fallback_topic_definitions: Mapping[str, TopicDefinition] | None = None,
    fallback_topic_aliases: Mapping[str, str] | None = None,
    jurisdiction_aliases: Tuple[str, ...] = (),
) -> DomainPack:
    manifest = _load_manifest(manifest_path)
    corpus = _manifest_mapping(manifest, "corpus")
    taxonomy = _manifest_mapping(manifest, "taxonomy")
    topic_definitions = _build_topic_definitions(taxonomy)
    if not topic_definitions and fallback_topic_definitions:
        topic_definitions = dict(fallback_topic_definitions)

    topic_aliases = _build_topic_aliases(topic_definitions)
    if not topic_aliases and fallback_topic_aliases:
        topic_aliases = dict(fallback_topic_aliases)

    overlays = _manifest_mapping(manifest, "overlays")
    prompt_overlay = _overlay_mapping(overlays, "prompt")
    validation_overlay = _overlay_mapping(overlays, "validation")
    jurisdiction = _manifest_mapping(manifest, "jurisdiction")
    subject = _manifest_mapping(manifest, "subject")

    pack_key = str(manifest.get("key") or Path(manifest_path).parent.name)
    jurisdiction_key = normalize_scope_token(str(jurisdiction.get("code", "")))
    subject_key = normalize_scope_token(str(subject.get("key", "tort")))
    raw_paths = corpus.get("raw_paths", fallback_raw_paths)
    if not isinstance(raw_paths, (list, tuple)):
        raw_paths = fallback_raw_paths
    normalized_raw_paths = tuple(str(path) for path in raw_paths if str(path).strip())
    if not normalized_raw_paths:
        normalized_raw_paths = fallback_raw_paths
    supplemental_paths = corpus.get("supplemental_paths", [])
    if not isinstance(supplemental_paths, (list, tuple)):
        supplemental_paths = []

    return DomainPack(
        key=pack_key,
        display_name=str(
            manifest.get("display_name") or pack_key.replace("_", " ").title()
        ),
        jurisdiction=Jurisdiction(
            key=jurisdiction_key,
            display_name=str(jurisdiction.get("name", jurisdiction_key.upper())),
            legal_system=str(jurisdiction.get("legal_system", "common_law")),
            aliases=_string_tuple(jurisdiction.get("aliases")) + jurisdiction_aliases,
        ),
        law_domain=subject_key,
        canonicalize_topic=lambda topic, aliases=topic_aliases: (
            _canonicalize_from_aliases(topic, aliases)
        ),
        is_supported_topic=lambda topic, aliases=topic_aliases, definitions=topic_definitions: (
            _canonicalize_from_aliases(topic, aliases) in definitions
        ),
        topic_keys=tuple(topic_definitions.keys()),
        topic_aliases=dict(topic_aliases),
        subject_label=str(subject.get("name", "Tort Law")),
        manifest_path=manifest_path,
        topic_definitions=dict(topic_definitions),
        prompt_overlay=dict(prompt_overlay),
        validation_overlay=dict(validation_overlay),
        corpus_path=str(corpus.get("clean_path", fallback_clean_path)),
        supplemental_corpus_paths=tuple(
            str(path) for path in supplemental_paths if str(path).strip()
        ),
        raw_paths=normalized_raw_paths,
        record_format=str(corpus.get("record_format", fallback_record_format)),
    )


_SG_TORT_MANIFEST_PATH = "corpus/packs/sg_tort/manifest.json"
_SG_TORT_FALLBACK_TOPIC_DEFINITIONS = {
    key: TopicDefinition(
        key=key,
        label=key.replace("_", " ").title(),
        category="",
        description="",
    )
    for key in all_tort_topic_keys()
}
_US_TORT_MANIFEST_PATH = "corpus/packs/us_tort/manifest.json"
_UK_TORT_MANIFEST_PATH = "corpus/packs/uk_tort/manifest.json"


DOMAIN_PACK_REGISTRY: Dict[str, DomainPack] = {}
for _pack in (
    _domain_pack_from_manifest(
        _SG_TORT_MANIFEST_PATH,
        fallback_clean_path="corpus/clean/tort/corpus.json",
        fallback_raw_paths=("corpus/raw/tort",),
        fallback_record_format="legacy_text_topic_v1",
        fallback_topic_definitions=_SG_TORT_FALLBACK_TOPIC_DEFINITIONS,
        fallback_topic_aliases=TOPIC_ALIASES,
        jurisdiction_aliases=(
            "singapore_law",
            "singapore tort",
            "singapore_tort",
        ),
    ),
    _domain_pack_from_manifest(
        _US_TORT_MANIFEST_PATH,
        fallback_clean_path="corpus/clean/us_tort/corpus.json",
        fallback_raw_paths=("corpus/raw/us_tort",),
        fallback_record_format="cap_case_json_v1",
        jurisdiction_aliases=(
            "united states",
            "united_states",
            "united states of america",
            "usa",
            "u.s.",
            "u.s.a.",
            "american tort",
        ),
    ),
    _domain_pack_from_manifest(
        _UK_TORT_MANIFEST_PATH,
        fallback_clean_path="corpus/clean/uk_tort/corpus.json",
        fallback_raw_paths=("corpus/raw/uk_tort",),
        fallback_record_format="tna_legaldocml_excerpt_v1",
        jurisdiction_aliases=(
            "united kingdom",
            "united_kingdom",
            "great britain",
            "england and wales",
            "england",
            "wales",
            "british tort",
        ),
    ),
):
    DOMAIN_PACK_REGISTRY[_pack.key] = _pack


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
    token = normalize_scope_token((key or "sg_tort").strip()) or "sg_tort"
    return get_domain_pack(token)
