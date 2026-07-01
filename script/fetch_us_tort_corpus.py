"""Fetch and normalize the starter US Tort CAP corpus."""

from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path
from typing import Any

import httpx

from src.corpus_ingestion import (
    DEFAULT_EVENTS_PATH,
    DEFAULT_HEALTH_PATH,
    CorpusParseError,
    fetch_http_json,
)

USER_AGENT = "jikai-us-tort-ingester/0.1"
CAP_TERMS_URL = "https://case.law/terms/"
CC0_URL = "https://creativecommons.org/publicdomain/zero/1.0/"
DEFAULT_OUTPUT = Path("corpus/clean/us_tort/corpus.json")

CURATED_CAP_CASES: tuple[dict[str, Any], ...] = (
    {
        "url": "https://static.case.law/ny/248/cases/0339-01.json",
        "topics": ["duty_of_care", "negligence", "remoteness"],
        "subtopics": ["foreseeability", "proximate_cause"],
    },
    {
        "url": "https://static.case.law/ny/217/cases/0382-01.json",
        "topics": ["product_liability", "negligence", "duty_of_care"],
        "subtopics": ["privity", "manufacturer_duty"],
    },
    {
        "url": "https://static.case.law/cal-2d/24/cases/0453-01.json",
        "topics": ["strict_liability", "product_liability"],
        "subtopics": ["defective_product", "manufacturer_liability"],
    },
    {
        "url": "https://static.case.law/cal-3d/17/cases/0425-01.json",
        "topics": ["duty_of_care", "negligence"],
        "subtopics": ["special_relationship", "foreseeable_victim"],
    },
    {
        "url": "https://static.case.law/cal-2d/33/cases/0080-01.json",
        "topics": ["causation", "negligence"],
        "subtopics": ["alternative_liability", "multiple_defendants"],
    },
)


def clean_text(value: str) -> str:
    text = value.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _casebody_opinion_text(payload: dict[str, Any]) -> str:
    casebody = payload.get("casebody", {})
    if not isinstance(casebody, dict):
        return ""
    opinions = casebody.get("opinions", [])
    if not isinstance(opinions, list):
        return ""
    texts = []
    for opinion in opinions:
        if not isinstance(opinion, dict):
            continue
        text = opinion.get("text", "")
        if isinstance(text, str) and text.strip():
            texts.append(text)
    return clean_text("\n\n".join(texts))


def _citation_values(payload: dict[str, Any]) -> list[str]:
    citations = payload.get("citations", [])
    if not isinstance(citations, list):
        return []
    values = []
    for citation in citations:
        if not isinstance(citation, dict):
            continue
        cite = str(citation.get("cite", "")).strip()
        if cite:
            values.append(cite)
    return values


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def record_from_cap_case(
    payload: dict[str, Any],
    *,
    source_url: str,
    topics: list[str],
    subtopics: list[str] | None = None,
    retrieved_at: str,
) -> dict[str, Any]:
    text = _casebody_opinion_text(payload)
    if not text:
        raise ValueError(f"CAP case has no opinion text: {source_url}")

    case_id = str(payload.get("id", "")).strip()
    if not case_id:
        raise ValueError(f"CAP case has no id: {source_url}")

    court = _mapping(payload.get("court"))
    jurisdiction = _mapping(payload.get("jurisdiction"))
    source = {
        "name": "Caselaw Access Project",
        "url": source_url,
        "terms_url": CAP_TERMS_URL,
        "source_format": "cap_static_json",
        "source_record_id": case_id,
        "retrieved_at": retrieved_at,
    }
    license_data = {
        "name": "CC0-1.0",
        "url": CC0_URL,
        "redistribution_status": "allowed",
        "attribution_required": False,
        "attribution_requested": True,
        "terms_url": CAP_TERMS_URL,
    }
    metadata = {
        "case_name": payload.get("name"),
        "case_abbreviation": payload.get("name_abbreviation"),
        "decision_date": payload.get("decision_date"),
        "docket_number": payload.get("docket_number"),
        "first_page": payload.get("first_page"),
        "last_page": payload.get("last_page"),
        "citations": _citation_values(payload),
        "court": {
            "id": court.get("id"),
            "name": court.get("name"),
            "name_abbreviation": court.get("name_abbreviation"),
        },
        "source_jurisdiction": {
            "id": jurisdiction.get("id"),
            "name": jurisdiction.get("name"),
            "name_long": jurisdiction.get("name_long"),
        },
        "last_updated": payload.get("last_updated"),
        "provenance": payload.get("provenance"),
        "source": source,
        "license": license_data,
    }
    return {
        "id": f"us_tort:cap:{case_id}",
        "corpus_pack_key": "us_tort",
        "jurisdiction": "us",
        "subject": "tort",
        "topics": _string_list(topics),
        "subtopics": _string_list(subtopics or []),
        "text": text,
        "source": source,
        "license": license_data,
        "metadata": metadata,
    }


def fetch_cap_case(
    client: httpx.Client,
    url: str,
    *,
    events_path: Path = DEFAULT_EVENTS_PATH,
    health_path: Path = DEFAULT_HEALTH_PATH,
) -> dict[str, Any]:
    payload = fetch_http_json(
        client,
        url,
        source="us_tort:cap",
        events_path=events_path,
        health_path=health_path,
    )
    if not isinstance(payload, dict):
        raise CorpusParseError(f"CAP response is not a JSON object: {url}")
    return payload


def build_records(
    case_specs: tuple[dict[str, Any], ...],
    *,
    retrieved_at: str,
    raw_dir: Path | None = None,
) -> list[dict[str, Any]]:
    records = []
    headers = {"User-Agent": USER_AGENT}
    with httpx.Client(headers=headers, follow_redirects=True, timeout=30.0) as client:
        for spec in case_specs:
            url = str(spec["url"])
            payload = fetch_cap_case(client, url)
            if raw_dir:
                raw_dir.mkdir(parents=True, exist_ok=True)
                case_id = str(payload.get("id", len(records))).strip()
                (raw_dir / f"{case_id}.json").write_text(
                    json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True)
                    + "\n",
                    encoding="utf-8",
                )
            records.append(
                record_from_cap_case(
                    payload,
                    source_url=url,
                    topics=_string_list(spec.get("topics")),
                    subtopics=_string_list(spec.get("subtopics")),
                    retrieved_at=retrieved_at,
                )
            )
    return records


def write_records(records: list[dict[str, Any]], output: Path) -> None:
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
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    records = build_records(
        CURATED_CAP_CASES,
        retrieved_at=args.retrieved_at,
        raw_dir=args.raw_dir,
    )
    if args.dry_run:
        print(json.dumps(records, indent=2, sort_keys=True, ensure_ascii=True))
        return 0
    write_records(records, args.output)
    print(f"Wrote {len(records)} records to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
