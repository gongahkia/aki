"""Build a blank blind-evaluation rater sheet from a packet manifest."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

from script.summarize_blind_eval_results import EXPECTED_HEADERS, LAW_TRAINED_PROFILES

SCORE_FIELDS = [
    "issue_spotting_coverage",
    "fact_sufficiency",
    "legal_ambiguity",
    "sg_law_fit",
    "answer_structure",
    "citation_rule_accuracy",
    "distractor_quality",
    "difficulty_calibration",
    "feedback_usefulness",
]


def _read_manifest(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("manifest root must be an object")
    return data


def _parse_rater(raw: str) -> tuple[str, str]:
    rater_id, sep, profile = raw.partition(":")
    rater_id = rater_id.strip()
    profile = profile.strip()
    if not sep or not rater_id or not profile:
        raise ValueError("--rater must use rater_id:profile")
    if profile not in LAW_TRAINED_PROFILES:
        raise ValueError(f"unknown law-trained rater profile: {profile}")
    return rater_id, profile


def _raters(raw_raters: list[str]) -> list[tuple[str, str]]:
    if not raw_raters:
        raise ValueError("at least one --rater is required")
    parsed = [_parse_rater(raw) for raw in raw_raters]
    rater_ids = [rater_id for rater_id, _ in parsed]
    duplicates = sorted(
        {rater_id for rater_id in rater_ids if rater_ids.count(rater_id) > 1}
    )
    if duplicates:
        raise ValueError("duplicate rater_id: " + ", ".join(duplicates))
    return parsed


def build_rater_sheet(
    manifest_path: Path,
    *,
    output_path: Path,
    raw_raters: list[str],
) -> Path:
    manifest = _read_manifest(manifest_path)
    packets = manifest.get("packets")
    if not isinstance(packets, list) or not packets:
        raise ValueError("manifest.packets must be a non-empty array")
    raters = _raters(raw_raters)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=EXPECTED_HEADERS)
        writer.writeheader()
        for packet in packets:
            packet_id = str(packet.get("packet_id", "")).strip()
            samples = packet.get("samples")
            if not packet_id:
                raise ValueError("packet_id is required")
            if not isinstance(samples, list) or len(samples) != 2:
                raise ValueError(f"{packet_id}: exactly two samples required")
            for rater_id, profile in raters:
                for sample in samples:
                    sample_id = str(sample.get("sample_id", "")).strip()
                    if not sample_id:
                        raise ValueError(f"{packet_id}: sample_id is required")
                    row = {
                        "packet_id": packet_id,
                        "sample_id": sample_id,
                        "rater_id": rater_id,
                        "rater_profile": profile,
                        "overall_preference": "",
                        "confidence": "",
                        "free_text_failure_modes": "",
                        "notes": "",
                    }
                    for field in SCORE_FIELDS:
                        row[field] = ""
                    writer.writerow(row)
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--rater",
        action="append",
        default=[],
        help="coarse rater assignment as rater_id:profile",
    )
    args = parser.parse_args()
    try:
        path = build_rater_sheet(
            args.manifest,
            output_path=args.output,
            raw_raters=args.rater,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
