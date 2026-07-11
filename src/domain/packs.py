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
class CourseProfile:
    """Educator-defined course/module profile scoped to a corpus pack."""

    key: str
    display_name: str
    corpus_pack_key: str
    syllabus_topics: Tuple[str, ...] = ()
    allowed_authority_ids: Tuple[str, ...] = ()
    difficulty_profile: Mapping[str, Any] | None = None
    exam_style: Mapping[str, Any] | None = None
    prompt_overlay: Mapping[str, Any] | None = None
    validation_overlay: Mapping[str, Any] | None = None
    data_backed: bool = False
    data_sources: Tuple[str, ...] = ()
    notes: str = ""


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
    course_profiles: Mapping[str, CourseProfile] | None = None
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


def _merge_overlay(
    base: Mapping[str, Any] | None,
    overlay: Mapping[str, Any] | None,
) -> Dict[str, Any]:
    merged = dict(base or {})
    for key, value in dict(overlay or {}).items():
        existing = merged.get(key)
        if isinstance(existing, dict) and isinstance(value, dict):
            nested = dict(existing)
            nested.update(value)
            merged[key] = nested
            continue
        if isinstance(existing, list) and isinstance(value, list):
            combined = list(existing)
            for item in value:
                if item not in combined:
                    combined.append(item)
            merged[key] = combined
            continue
        merged[key] = value
    return merged


def _build_course_profiles(
    manifest: Mapping[str, Any],
    *,
    pack_key: str,
    topic_aliases: Mapping[str, str],
    topic_definitions: Mapping[str, TopicDefinition],
) -> Dict[str, CourseProfile]:
    raw_profiles = manifest.get("course_profiles", {})
    if isinstance(raw_profiles, dict):
        profile_items: list[tuple[str, Any]] = list(raw_profiles.items())
    elif isinstance(raw_profiles, list):
        profile_items = [
            (str(item.get("key", "")), item)
            for item in raw_profiles
            if isinstance(item, dict)
        ]
    else:
        return {}

    profiles: Dict[str, CourseProfile] = {}
    for raw_key, raw_profile in profile_items:
        if not isinstance(raw_profile, dict):
            continue
        key = normalize_scope_token(str(raw_profile.get("key") or raw_key))
        if not key:
            continue
        syllabus_topics: list[str] = []
        raw_syllabus = raw_profile.get("syllabus_topics", [])
        if isinstance(raw_syllabus, (list, tuple)):
            for topic in raw_syllabus:
                canonical = _canonicalize_from_aliases(str(topic), topic_aliases)
                if canonical in topic_definitions and canonical not in syllabus_topics:
                    syllabus_topics.append(canonical)
        overlays = _manifest_mapping(raw_profile, "overlays")
        difficulty_profile = _manifest_mapping(raw_profile, "difficulty_profile")
        exam_style = _manifest_mapping(raw_profile, "exam_style")
        profiles[key] = CourseProfile(
            key=key,
            display_name=str(
                raw_profile.get("display_name") or key.replace("_", " ").title()
            ),
            corpus_pack_key=pack_key,
            syllabus_topics=tuple(syllabus_topics),
            allowed_authority_ids=_string_tuple(
                raw_profile.get("allowed_authority_ids")
            ),
            difficulty_profile=difficulty_profile,
            exam_style=exam_style,
            prompt_overlay=_overlay_mapping(overlays, "prompt"),
            validation_overlay=_overlay_mapping(overlays, "validation"),
            data_backed=bool(raw_profile.get("data_backed", False)),
            data_sources=_string_tuple(raw_profile.get("data_sources")),
            notes=str(raw_profile.get("notes", "")),
        )
    return profiles


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
    course_profiles = _build_course_profiles(
        manifest,
        pack_key=pack_key,
        topic_aliases=topic_aliases,
        topic_definitions=topic_definitions,
    )

    def canonicalize_manifest_topic(topic: str) -> str:
        return _canonicalize_from_aliases(topic, topic_aliases)

    def is_supported_manifest_topic(topic: str) -> bool:
        return _canonicalize_from_aliases(topic, topic_aliases) in topic_definitions

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
        canonicalize_topic=canonicalize_manifest_topic,
        is_supported_topic=is_supported_manifest_topic,
        topic_keys=tuple(topic_definitions.keys()),
        topic_aliases=dict(topic_aliases),
        subject_label=str(subject.get("name", "Tort Law")),
        manifest_path=manifest_path,
        topic_definitions=dict(topic_definitions),
        prompt_overlay=dict(prompt_overlay),
        validation_overlay=dict(validation_overlay),
        course_profiles=course_profiles,
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


def list_course_profiles(corpus_pack: str | None = None) -> Tuple[CourseProfile, ...]:
    """List course profiles, optionally scoped to one corpus pack."""
    packs = (resolve_domain_pack(corpus_pack),) if corpus_pack else list_domain_packs()
    profiles: list[CourseProfile] = []
    for pack in packs:
        profiles.extend((pack.course_profiles or {}).values())
    return tuple(profiles)


def get_course_profile(corpus_pack: str, course_profile: str) -> CourseProfile:
    """Fetch a course profile by corpus pack and profile key."""
    pack = resolve_domain_pack(corpus_pack)
    token = normalize_scope_token(course_profile)
    profiles = pack.course_profiles or {}
    if token not in profiles:
        raise KeyError(
            f"Unknown course_profile '{course_profile}' for corpus_pack '{pack.key}'"
        )
    return profiles[token]


def resolve_course_profile(
    corpus_pack: str,
    course_profile: str | None = None,
) -> CourseProfile | None:
    """Resolve an optional course profile."""
    if not course_profile:
        return None
    return get_course_profile(corpus_pack, course_profile)


def _require_data_backed_profile(profile: CourseProfile) -> None:
    if not profile.data_backed:
        raise ValueError(
            f"course_profile '{profile.key}' is not data-backed for "
            f"corpus_pack '{profile.corpus_pack_key}'"
        )


def resolve_prompt_overlay(
    corpus_pack: str,
    course_profile: str | None = None,
) -> Dict[str, Any]:
    """Merge pack prompt overlay with an optional course-profile overlay."""
    pack = resolve_domain_pack(corpus_pack)
    profile = resolve_course_profile(pack.key, course_profile)
    if profile is None:
        return dict(pack.prompt_overlay or {})
    _require_data_backed_profile(profile)
    return _merge_overlay(pack.prompt_overlay, profile.prompt_overlay)


def resolve_validation_overlay(
    corpus_pack: str,
    course_profile: str | None = None,
) -> Dict[str, Any]:
    """Merge pack validation overlay with an optional course-profile overlay."""
    pack = resolve_domain_pack(corpus_pack)
    profile = resolve_course_profile(pack.key, course_profile)
    if profile is None:
        return dict(pack.validation_overlay or {})
    _require_data_backed_profile(profile)
    return _merge_overlay(pack.validation_overlay, profile.validation_overlay)


def default_domain_pack() -> DomainPack:
    """Return the default domain pack used by current services."""
    return get_domain_pack("sg_tort")


def resolve_domain_pack(key: str | None = None) -> DomainPack:
    """Fetch requested pack or default to SG Tort."""
    token = normalize_scope_token((key or "sg_tort").strip()) or "sg_tort"
    return get_domain_pack(token)
