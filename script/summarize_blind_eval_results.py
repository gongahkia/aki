"""Summarize completed blind-evaluation rating sheets."""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

EXPECTED_HEADERS = [
    "packet_id",
    "sample_id",
    "rater_id",
    "rater_profile",
    "doctrinal_accuracy",
    "factual_richness",
    "issue_coverage",
    "explanation_quality",
    "difficulty_calibration",
    "usefulness_for_study",
    "jurisdiction_fit",
    "overall_preference",
    "confidence",
    "free_text_failure_modes",
    "notes",
]

DIMENSION_WEIGHTS = {
    "doctrinal_accuracy": 25,
    "issue_coverage": 20,
    "factual_richness": 15,
    "explanation_quality": 15,
    "difficulty_calibration": 10,
    "usefulness_for_study": 10,
    "jurisdiction_fit": 5,
}

PREFERENCES = {"sample_a", "sample_b", "tie", "no_preference"}


def _read_ratings(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != EXPECTED_HEADERS:
            raise ValueError(f"{path} header mismatch")
        return list(reader)


def _read_manifest(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _sample_sources(manifest: dict[str, Any]) -> dict[str, str]:
    sources: dict[str, str] = {}
    for packet in manifest.get("packets", []):
        for sample in packet.get("samples", []):
            sample_id = str(sample.get("sample_id", ""))
            if sample_id:
                sources[sample_id] = str(sample.get("source", "unknown"))
    return sources


def _score(value: str, *, field: str, row_index: int) -> int:
    try:
        score = int(value)
    except ValueError as exc:
        raise ValueError(f"row {row_index}: {field} must be an int") from exc
    if score < 1 or score > 5:
        raise ValueError(f"row {row_index}: {field} must be 1..5")
    return score


def _weighted_score(row: dict[str, str], row_index: int) -> float:
    total = 0
    for field, weight in DIMENSION_WEIGHTS.items():
        total += _score(row[field], field=field, row_index=row_index) * weight
    return round(total / 5, 3)


def _split_failures(raw: str) -> list[str]:
    return [
        item.strip().lower()
        for item in raw.replace(";", "|").split("|")
        if item.strip()
    ]


def summarize(
    ratings_path: Path,
    *,
    manifest_path: Path | None = None,
    require_publishable: bool = False,
) -> dict[str, Any]:
    rows = _read_ratings(ratings_path)
    if not rows:
        raise ValueError("no rating rows found")

    manifest = _read_manifest(manifest_path)
    sample_sources = _sample_sources(manifest)
    rater_profiles: Counter[str] = Counter()
    preferences: Counter[str] = Counter()
    failures: Counter[str] = Counter()
    dimension_scores: dict[str, list[int]] = defaultdict(list)
    sample_scores: dict[str, list[float]] = defaultdict(list)
    packet_ids: set[str] = set()
    raters: set[str] = set()

    for idx, row in enumerate(rows, start=2):
        packet_id = row["packet_id"].strip()
        sample_id = row["sample_id"].strip()
        rater_id = row["rater_id"].strip()
        preference = row["overall_preference"].strip()
        if not packet_id or not sample_id or not rater_id:
            raise ValueError(f"row {idx}: packet_id, sample_id, rater_id required")
        if preference not in PREFERENCES:
            raise ValueError(f"row {idx}: invalid overall_preference")
        packet_ids.add(packet_id)
        raters.add(rater_id)
        rater_profiles[row["rater_profile"].strip() or "unknown"] += 1
        preferences[preference] += 1
        for field in DIMENSION_WEIGHTS:
            dimension_scores[field].append(
                _score(row[field], field=field, row_index=idx)
            )
        weighted = _weighted_score(row, idx)
        sample_scores[sample_id].append(weighted)
        failures.update(_split_failures(row["free_text_failure_modes"]))

    if require_publishable and len(raters) < 3:
        raise ValueError("publishable pilot requires at least 3 distinct raters")

    return {
        "schema_version": "jikai.blind_eval.summary.v1",
        "rubric_version": manifest.get("rubric_version", "1.0"),
        "sample_size": len(packet_ids),
        "rating_rows": len(rows),
        "rater_count": len(raters),
        "rater_profiles": dict(sorted(rater_profiles.items())),
        "anonymization_method": "packet/sample/rater IDs only",
        "blinding_method": "source labels hidden from raters",
        "dimension_distribution": _dimension_distribution(dimension_scores),
        "weighted_score_distribution": _weighted_distribution(
            sample_scores, sample_sources
        ),
        "preference_distribution": dict(sorted(preferences.items())),
        "failure_modes": dict(sorted(failures.items())),
        "publishable": len(raters) >= 3,
        "claims_permitted": [],
        "claims_blocked": (
            ["all public comparative quality claims"] if len(raters) < 3 else []
        ),
    }


def _dimension_distribution(scores: dict[str, list[int]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for field, values in scores.items():
        out[field] = {
            "mean": round(statistics.fmean(values), 3),
            "counts": {str(score): values.count(score) for score in range(1, 6)},
        }
    return out


def _weighted_distribution(
    sample_scores: dict[str, list[float]], sample_sources: dict[str, str]
) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for sample_id, values in sorted(sample_scores.items()):
        out[sample_id] = {
            "source": sample_sources.get(sample_id, "unknown"),
            "mean": round(statistics.fmean(values), 3),
            "min": round(min(values), 3),
            "max": round(max(values), 3),
            "n": len(values),
        }
    return out


def write_markdown(summary: dict[str, Any], path: Path) -> None:
    lines = [
        "# Blind Evaluation Summary",
        "",
        f"Rubric version: {summary['rubric_version']}",
        f"Sample size: {summary['sample_size']}",
        f"Rater count: {summary['rater_count']}",
        f"Publishable: {str(summary['publishable']).lower()}",
        "",
        "## Rater Profiles",
        "",
    ]
    for profile, count in summary["rater_profiles"].items():
        lines.append(f"- {profile}: {count}")
    lines.extend(["", "## Weighted Scores", ""])
    lines.append("| Sample | Source | Mean | Min | Max | N |")
    lines.append("|---|---|---:|---:|---:|---:|")
    for sample_id, stats in summary["weighted_score_distribution"].items():
        lines.append(
            f"| {sample_id} | {stats['source']} | {stats['mean']} | "
            f"{stats['min']} | {stats['max']} | {stats['n']} |"
        )
    lines.extend(["", "## Preferences", ""])
    for preference, count in summary["preference_distribution"].items():
        lines.append(f"- {preference}: {count}")
    lines.extend(["", "## Failure Modes", ""])
    if summary["failure_modes"]:
        for mode, count in summary["failure_modes"].items():
            lines.append(f"- {mode}: {count}")
    else:
        lines.append("- none recorded")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ratings", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--markdown", type=Path)
    parser.add_argument("--require-publishable", action="store_true")
    args = parser.parse_args()

    try:
        summary = summarize(
            args.ratings,
            manifest_path=args.manifest,
            require_publishable=args.require_publishable,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.output:
        args.output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    if args.markdown:
        write_markdown(summary, args.markdown)
    if not args.output and not args.markdown:
        print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
