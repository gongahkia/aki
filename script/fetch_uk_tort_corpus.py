"""Fetch and normalize the starter UK Tort TNA corpus."""

from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

import httpx

from src.corpus_ingestion import (
    DEFAULT_EVENTS_PATH,
    DEFAULT_HEALTH_PATH,
    fetch_http_text,
)
from src.corpus_source_registry import (
    assert_records_text_commit_allowed,
    assert_text_commit_allowed,
)

USER_AGENT = "jikai-uk-tort-ingester/0.1"
TNA_SOURCE_ID = "tna_find_case_law_xml"
OJL_URL = "https://caselaw.nationalarchives.gov.uk/open-justice-licence/version/2"
DEFAULT_OUTPUT = Path("corpus/clean/uk_tort/corpus.json")
DEFAULT_MAX_TEXT_CHARS = 12000

CURATED_TNA_CASES: tuple[dict[str, Any], ...] = (
    {
        "url": "https://caselaw.nationalarchives.gov.uk/uksc/2018/4/data.xml",
        "topics": ["duty_of_care", "negligence"],
        "subtopics": ["caparo_test", "public_authority"],
    },
    {
        "url": "https://caselaw.nationalarchives.gov.uk/uksc/2021/20/data.xml",
        "topics": ["economic_loss", "negligence", "duty_of_care"],
        "subtopics": ["professional_negligence", "scope_of_duty"],
    },
    {
        "url": "https://caselaw.nationalarchives.gov.uk/uksc/2021/21/data.xml",
        "topics": ["standard_of_care", "causation", "negligence"],
        "subtopics": ["clinical_negligence", "scope_of_duty"],
    },
    {
        "url": "https://caselaw.nationalarchives.gov.uk/uksc/2024/1/data.xml",
        "topics": ["psychiatric_harm", "negligence", "duty_of_care"],
        "subtopics": ["secondary_victim", "control_mechanisms"],
    },
    {
        "url": "https://caselaw.nationalarchives.gov.uk/uksc/2020/12/data.xml",
        "topics": ["vicarious_liability", "negligence"],
        "subtopics": ["close_connection", "course_of_employment"],
    },
)


def clean_text(value: str) -> str:
    text = value.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _first_text(root: ET.Element, local_name: str) -> str:
    for element in root.iter():
        if _local_name(element.tag) == local_name:
            text = clean_text(" ".join(part for part in element.itertext()))
            if text:
                return text
    return ""


def _first_attr(root: ET.Element, local_name: str, attr: str) -> str:
    for element in root.iter():
        if _local_name(element.tag) == local_name:
            value = str(element.attrib.get(attr, "")).strip()
            if value:
                return value
    return ""


def _frbr_value(root: ET.Element, local_name: str, attr: str = "value") -> str:
    return _first_attr(root, local_name, attr)


def _uk_metadata_text(root: ET.Element, local_name: str) -> str:
    for element in root.iter():
        if _local_name(element.tag) == local_name:
            text = clean_text(" ".join(part for part in element.itertext()))
            if text:
                return text
    return ""


def _judgment_body_text(root: ET.Element) -> str:
    for element in root.iter():
        if _local_name(element.tag) == "judgmentBody":
            return clean_text("\n".join(part for part in element.itertext()))
    return clean_text("\n".join(part for part in root.itertext()))


def _capped_text(text: str, max_chars: int) -> tuple[str, bool]:
    if max_chars <= 0 or len(text) <= max_chars:
        return text, False
    clipped = text[:max_chars].rsplit(" ", 1)[0].rstrip()
    return f"{clipped}\n\n[truncated from source]", True


def record_from_tna_xml(
    xml_text: str,
    *,
    source_url: str,
    topics: list[str],
    subtopics: list[str] | None = None,
    retrieved_at: str,
    max_text_chars: int = DEFAULT_MAX_TEXT_CHARS,
) -> dict[str, Any]:
    root = ET.fromstring(xml_text.encode("utf-8"))
    case_name = _frbr_value(root, "FRBRname") or _first_text(root, "party")
    neutral_citation = _first_text(root, "neutralCitation") or _uk_metadata_text(
        root, "cite"
    )
    document_uri = _frbr_value(root, "FRBRuri") or source_url.removesuffix("/data.xml")
    judgment_date = _first_attr(root, "FRBRdate", "date") or _first_attr(
        root, "docDate", "date"
    )
    transform_date = ""
    for element in root.iter():
        if (
            _local_name(element.tag) == "FRBRdate"
            and element.attrib.get("name") == "transform"
        ):
            transform_date = str(element.attrib.get("date", "")).strip()
            break
    content_hash = _uk_metadata_text(root, "hash")
    court = _uk_metadata_text(root, "court") or _first_text(root, "courtType")
    body_text = _judgment_body_text(root)
    if not body_text:
        raise ValueError(f"TNA judgment has no body text: {source_url}")

    header = "\n".join(
        value for value in (case_name, neutral_citation, court, judgment_date) if value
    )
    capped_text, truncated = _capped_text(
        clean_text(f"{header}\n\n{body_text}"),
        max_text_chars,
    )
    source = {
        "source_id": TNA_SOURCE_ID,
        "name": "The National Archives Find Case Law",
        "url": source_url.removesuffix("/data.xml"),
        "data_url": source_url,
        "terms_url": OJL_URL,
        "source_format": "tna_legaldocml_xml",
        "retrieved_at": retrieved_at,
    }
    license_data = {
        "name": "Open Justice Licence v2.0",
        "url": OJL_URL,
        "redistribution_status": "allowed",
        "attribution_required": True,
        "computational_analysis_requires_permission": True,
        "terms_url": OJL_URL,
    }
    source_key = document_uri.removeprefix("https://caselaw.nationalarchives.gov.uk/")
    source_key = source_key.replace("/", ":")
    provenance = {
        "source_id": TNA_SOURCE_ID,
        "source_url": source["url"],
        "data_url": source_url,
        "retrieved_at": retrieved_at,
        "terms_url": OJL_URL,
        "content_hash": content_hash,
        "document_uri": document_uri,
        "neutral_citation": neutral_citation,
        "decision_date": judgment_date,
    }
    metadata = {
        "case_name": case_name,
        "neutral_citation": neutral_citation,
        "court": court,
        "decision_date": judgment_date,
        "transform_date": transform_date,
        "document_uri": document_uri,
        "content_hash": content_hash,
        "text_scope": "capped_excerpt" if truncated else "full_text",
        "max_text_chars": max_text_chars,
        "current_version_required": True,
        "computational_analysis_requires_permission": True,
        "provenance": provenance,
        "source": source,
        "license": license_data,
    }
    return {
        "id": f"uk_tort:tna:{source_key}",
        "corpus_pack_key": "uk_tort",
        "jurisdiction": "uk",
        "subject": "tort",
        "topics": _string_list(topics),
        "subtopics": _string_list(subtopics or []),
        "text": capped_text,
        "source": source,
        "provenance": provenance,
        "license": license_data,
        "metadata": metadata,
    }


def fetch_tna_xml(
    client: httpx.Client,
    url: str,
    *,
    events_path: Path = DEFAULT_EVENTS_PATH,
    health_path: Path = DEFAULT_HEALTH_PATH,
) -> str:
    return fetch_http_text(
        client,
        url,
        source="uk_tort:tna",
        events_path=events_path,
        health_path=health_path,
    )


def build_records(
    case_specs: tuple[dict[str, Any], ...],
    *,
    retrieved_at: str,
    raw_dir: Path | None = None,
    max_text_chars: int = DEFAULT_MAX_TEXT_CHARS,
) -> list[dict[str, Any]]:
    assert_text_commit_allowed(TNA_SOURCE_ID)
    records = []
    headers = {"User-Agent": USER_AGENT}
    with httpx.Client(headers=headers, follow_redirects=True, timeout=30.0) as client:
        for spec in case_specs:
            url = str(spec["url"])
            xml_text = fetch_tna_xml(client, url)
            if raw_dir:
                raw_dir.mkdir(parents=True, exist_ok=True)
                raw_name = url.removeprefix("https://caselaw.nationalarchives.gov.uk/")
                raw_name = raw_name.replace("/", "_")
                (raw_dir / raw_name).write_text(xml_text, encoding="utf-8")
            records.append(
                record_from_tna_xml(
                    xml_text,
                    source_url=url,
                    topics=_string_list(spec.get("topics")),
                    subtopics=_string_list(spec.get("subtopics")),
                    retrieved_at=retrieved_at,
                    max_text_chars=max_text_chars,
                )
            )
    return records


def write_records(records: list[dict[str, Any]], output: Path) -> None:
    assert_records_text_commit_allowed(records)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(records, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--raw-dir", type=Path, default=None)
    parser.add_argument("--retrieved-at", default=date.today().isoformat())
    parser.add_argument("--max-text-chars", type=int, default=DEFAULT_MAX_TEXT_CHARS)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    records = build_records(
        CURATED_TNA_CASES,
        retrieved_at=args.retrieved_at,
        raw_dir=args.raw_dir,
        max_text_chars=args.max_text_chars,
    )
    if args.dry_run:
        print(json.dumps(records, indent=2, sort_keys=True, ensure_ascii=True))
        return 0
    write_records(records, args.output)
    print(f"Wrote {len(records)} records to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
