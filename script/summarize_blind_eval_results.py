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
    "issue_spotting_coverage",
    "fact_sufficiency",
    "legal_ambiguity",
    "sg_law_fit",
    "answer_structure",
    "citation_rule_accuracy",
    "distractor_quality",
    "difficulty_calibration",
    "feedback_usefulness",
    "overall_preference",
    "confidence",
    "free_text_failure_modes",
    "notes",
]

DIMENSION_WEIGHTS = {
    "issue_spotting_coverage": 20,
    "fact_sufficiency": 12,
    "legal_ambiguity": 10,
    "sg_law_fit": 12,
    "answer_structure": 10,
    "citation_rule_accuracy": 20,
    "distractor_quality": 6,
    "difficulty_calibration": 5,
    "feedback_usefulness": 5,
}

PREFERENCES = {"sample_a", "sample_b", "tie", "no_preference"}
LAW_TRAINED_PROFILES = {
    "law_student",
    "law_student_1l",
    "law_student_2l",
    "law_student_3l",
    "law_graduate",
    "trainee_lawyer",
    "lawyer",
    "legal_academic",
    "solicitor",
    "barrister",
}
DEFAULT_MIN_SAMPLES = 30
DEFAULT_MIN_RATERS_PER_ITEM = 2


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
    min_samples: int = DEFAULT_MIN_SAMPLES,
    min_raters_per_item: int = DEFAULT_MIN_RATERS_PER_ITEM,
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
    sample_dimension_scores: dict[str, dict[str, list[int]]] = defaultdict(
        lambda: defaultdict(list)
    )
    packet_ids: set[str] = set()
    packet_raters: dict[str, set[str]] = defaultdict(set)
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
        packet_raters[packet_id].add(rater_id)
        raters.add(rater_id)
        rater_profiles[row["rater_profile"].strip() or "unknown"] += 1
        preferences[preference] += 1
        for field in DIMENSION_WEIGHTS:
            value = _score(row[field], field=field, row_index=idx)
            dimension_scores[field].append(value)
            sample_dimension_scores[sample_id][field].append(value)
        weighted = _weighted_score(row, idx)
        sample_scores[sample_id].append(weighted)
        failures.update(_split_failures(row["free_text_failure_modes"]))

    publishability_errors = _publishability_errors(
        packet_ids=packet_ids,
        packet_raters=packet_raters,
        rater_profiles=set(rater_profiles),
        min_samples=min_samples,
        min_raters_per_item=min_raters_per_item,
    )
    if require_publishable and publishability_errors:
        raise ValueError("; ".join(publishability_errors))

    return {
        "schema_version": "jikai.blind_eval.summary.v1",
        "rubric_version": manifest.get("rubric_version", "1.0"),
        "sample_size": len(packet_ids),
        "rating_rows": len(rows),
        "rater_count": len(raters),
        "rater_profiles": dict(sorted(rater_profiles.items())),
        "min_samples_required": min_samples,
        "min_raters_per_item_required": min_raters_per_item,
        "items_with_min_raters": sum(
            1
            for packet_id in packet_ids
            if len(packet_raters[packet_id]) >= min_raters_per_item
        ),
        "items_missing_min_raters": sorted(
            packet_id
            for packet_id in packet_ids
            if len(packet_raters[packet_id]) < min_raters_per_item
        ),
        "anonymization_method": "packet/sample/rater IDs only",
        "blinding_method": "source labels hidden from raters",
        "dimension_distribution": _dimension_distribution(dimension_scores),
        "weighted_score_distribution": _weighted_distribution(
            sample_scores, sample_sources
        ),
        "inter_rater_agreement": _inter_rater_agreement(sample_dimension_scores),
        "preference_distribution": dict(sorted(preferences.items())),
        "failure_modes": dict(sorted(failures.items())),
        "publishable": not publishability_errors,
        "publishability_errors": publishability_errors,
        "claims_permitted": [] if publishability_errors else ["narrow evaluated scope"],
        "claims_blocked": publishability_errors,
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


def _publishability_errors(
    *,
    packet_ids: set[str],
    packet_raters: dict[str, set[str]],
    rater_profiles: set[str],
    min_samples: int,
    min_raters_per_item: int,
) -> list[str]:
    errors: list[str] = []
    if len(packet_ids) < min_samples:
        errors.append(
            f"publishable pilot requires at least {min_samples} held-out items"
        )
    missing = sorted(
        packet_id
        for packet_id in packet_ids
        if len(packet_raters[packet_id]) < min_raters_per_item
    )
    if missing:
        errors.append(
            "publishable pilot requires at least "
            f"{min_raters_per_item} distinct raters per item; missing: "
            + ", ".join(missing)
        )
    invalid_profiles = sorted(rater_profiles - LAW_TRAINED_PROFILES)
    if invalid_profiles:
        errors.append(
            "publishable pilot requires law-trained rater profiles; invalid: "
            + ", ".join(invalid_profiles)
        )
    return errors


def _inter_rater_agreement(
    sample_dimension_scores: dict[str, dict[str, list[int]]]
) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for field in DIMENSION_WEIGHTS:
        deltas: list[int] = []
        exact_matches = 0
        pair_count = 0
        rated_items = 0
        for scores_by_dimension in sample_dimension_scores.values():
            scores = scores_by_dimension.get(field, [])
            if len(scores) < 2:
                continue
            rated_items += 1
            for left_index, left in enumerate(scores):
                for right in scores[left_index + 1 :]:
                    pair_count += 1
                    delta = abs(left - right)
                    deltas.append(delta)
                    if delta == 0:
                        exact_matches += 1
        out[field] = {
            "rated_items": rated_items,
            "pair_count": pair_count,
            "exact_match_rate": (
                round(exact_matches / pair_count, 3) if pair_count else None
            ),
            "mean_abs_delta": round(statistics.fmean(deltas), 3) if deltas else None,
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
        f"Minimum held-out items required: {summary['min_samples_required']}",
        "Minimum distinct raters per item required: "
        f"{summary['min_raters_per_item_required']}",
        "",
        "## Publishability Gates",
        "",
    ]
    if summary["publishability_errors"]:
        for error in summary["publishability_errors"]:
            lines.append(f"- blocked: {error}")
    else:
        lines.append("- passed")
    lines.extend(
        [
            "",
            "## Rater Profiles",
            "",
        ]
    )
    for profile, count in summary["rater_profiles"].items():
        lines.append(f"- {profile}: {count}")
    lines.extend(["", "## Inter-Rater Agreement", ""])
    lines.append("| Dimension | Rated Items | Pairs | Exact Match | Mean Abs Delta |")
    lines.append("|---|---:|---:|---:|---:|")
    for field, stats in summary["inter_rater_agreement"].items():
        lines.append(
            f"| {field} | {stats['rated_items']} | {stats['pair_count']} | "
            f"{stats['exact_match_rate']} | {stats['mean_abs_delta']} |"
        )
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
    parser.add_argument("--min-samples", type=int, default=DEFAULT_MIN_SAMPLES)
    parser.add_argument(
        "--min-raters-per-item", type=int, default=DEFAULT_MIN_RATERS_PER_ITEM
    )
    args = parser.parse_args()

    try:
        summary = summarize(
            args.ratings,
            manifest_path=args.manifest,
            require_publishable=args.require_publishable,
            min_samples=args.min_samples,
            min_raters_per_item=args.min_raters_per_item,
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
