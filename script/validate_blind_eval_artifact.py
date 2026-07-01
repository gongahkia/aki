"""Validate blind-evaluation protocol artifacts."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any


EXPECTED_RATER_HEADERS = [
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

REQUIRED_RUBRIC_TERMS = [
    "Rubric version: 1.0",
    "doctrinal accuracy",
    "factual richness",
    "issue coverage",
    "explanation quality",
    "difficulty calibration",
    "usefulness for study",
    "jurisdiction fit",
    "At least three legally trained raters",
    "Baseline Source Policy",
    "Claim Gate",
    "Quimbee terms",
    "Studicata terms",
]

REQUIRED_PILOT_TERMS = [
    "human ratings pending",
    "human sample size | 0",
    "claims permitted | none",
    "#14 cannot be closed from repo work alone",
]


def _read_text(path: Path, errors: list[str]) -> str:
    if not path.exists():
        errors.append(f"missing file: {path}")
        return ""
    return path.read_text(encoding="utf-8")


def validate_markdown_terms(path: Path, required_terms: list[str]) -> list[str]:
    errors: list[str] = []
    text = _read_text(path, errors)
    for term in required_terms:
        if term not in text:
            errors.append(f"{path} missing required term: {term}")
    return errors


def validate_rater_sheet(path: Path) -> list[str]:
    errors: list[str] = []
    if not path.exists():
        return [f"missing file: {path}"]
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    if not rows:
        return [f"{path} is empty"]
    if rows[0] != EXPECTED_RATER_HEADERS:
        errors.append(f"{path} header mismatch")
    return errors


def _require_mapping(value: Any, name: str, errors: list[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        errors.append(f"{name} must be an object")
        return {}
    return value


def validate_sample_manifest_template(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        data = json.loads(_read_text(path, errors))
    except json.JSONDecodeError as exc:
        return [f"{path} invalid JSON: {exc}"]
    if errors:
        return errors
    manifest = _require_mapping(data, "manifest", errors)
    for key in (
        "schema_version",
        "rubric_version",
        "jurisdiction",
        "subject",
        "corpus_pack_key",
        "corpus_pack_revision",
        "packet_randomization",
        "baseline",
        "packets",
    ):
        if key not in manifest:
            errors.append(f"manifest.{key} is required")
    randomization = _require_mapping(
        manifest.get("packet_randomization"), "packet_randomization", errors
    )
    if randomization.get("source_labels_visible_to_raters") is not False:
        errors.append("packet_randomization.source_labels_visible_to_raters must be false")
    baseline = _require_mapping(manifest.get("baseline"), "baseline", errors)
    if "Quimbee or Studicata" not in str(baseline.get("notes", "")):
        errors.append("baseline.notes must preserve incumbent permission warning")
    packets = manifest.get("packets")
    if not isinstance(packets, list) or not packets:
        errors.append("manifest.packets must be a non-empty array")
    return errors


def validate_eval_artifacts(repo_root: Path) -> list[str]:
    eval_dir = repo_root / "docs" / "evals"
    errors: list[str] = []
    errors.extend(
        validate_markdown_terms(
            eval_dir / "blind-eval-rubric-v1.md", REQUIRED_RUBRIC_TERMS
        )
    )
    errors.extend(
        validate_markdown_terms(
            eval_dir / "blind-eval-pilot-0-readiness-2026-07-01.md",
            REQUIRED_PILOT_TERMS,
        )
    )
    errors.extend(validate_rater_sheet(eval_dir / "blind-eval-rater-sheet.csv"))
    errors.extend(
        validate_sample_manifest_template(
            eval_dir / "blind-eval-sample-manifest.template.json"
        )
    )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    args = parser.parse_args()

    errors = validate_eval_artifacts(args.repo_root)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("OK: blind eval artifacts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
