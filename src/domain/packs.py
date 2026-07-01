"""Domain-pack registry for jurisdiction-specific legal modules."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Tuple

from .topics import (
    TOPIC_ALIASES,
    all_tort_topic_keys,
    canonicalize_topic,
    is_tort_topic,
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


_SG_TORT_MANIFEST_PATH = "corpus/packs/sg_tort/manifest.json"
_SG_TORT_MANIFEST = _load_manifest(_SG_TORT_MANIFEST_PATH)
_SG_TORT_CORPUS = _SG_TORT_MANIFEST.get("corpus", {})
if not isinstance(_SG_TORT_CORPUS, dict):
    _SG_TORT_CORPUS = {}


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
        canonicalize_topic=canonicalize_topic,
        is_supported_topic=is_tort_topic,
        topic_keys=all_tort_topic_keys(),
        topic_aliases=dict(TOPIC_ALIASES),
        manifest_path=_SG_TORT_MANIFEST_PATH,
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
