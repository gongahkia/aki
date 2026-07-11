import csv
import json

import pytest

from script.summarize_blind_eval_results import (
    EXPECTED_HEADERS,
    summarize,
    write_markdown,
)


def _write_rows(path, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=EXPECTED_HEADERS)
        writer.writeheader()
        writer.writerows(rows)


def _row(packet, sample, rater, preference="sample_a"):
    return {
        "packet_id": packet,
        "sample_id": sample,
        "rater_id": rater,
        "rater_profile": "law_graduate",
        "issue_spotting_coverage": "5",
        "fact_sufficiency": "4",
        "legal_ambiguity": "4",
        "sg_law_fit": "5",
        "answer_structure": "4",
        "citation_rule_accuracy": "5",
        "distractor_quality": "3",
        "difficulty_calibration": "3",
        "feedback_usefulness": "5",
        "overall_preference": preference,
        "confidence": "4",
        "free_text_failure_modes": "shallow facts|weak difficulty calibration",
        "notes": "",
    }


def test_summarize_completed_sheet(tmp_path):
    ratings = tmp_path / "ratings.csv"
    manifest = tmp_path / "manifest.json"
    _write_rows(
        ratings,
        [
            _row("p1", "p1-a", "r1"),
            _row("p1", "p1-b", "r2", preference="sample_b"),
            _row("p2", "p2-a", "r3", preference="tie"),
            _row("p2", "p2-b", "r1", preference="tie"),
        ],
    )
    manifest.write_text(
        json.dumps(
            {
                "rubric_version": "1.0",
                "packets": [
                    {
                        "samples": [
                            {"sample_id": "p1-a", "source": "jikai"},
                            {"sample_id": "p1-b", "source": "baseline"},
                        ]
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    summary = summarize(
        ratings,
        manifest_path=manifest,
        require_publishable=True,
        min_samples=2,
    )

    assert summary["sample_size"] == 2
    assert summary["rater_count"] == 3
    assert summary["publishable"] is True
    assert summary["items_with_min_raters"] == 2
    assert summary["weighted_score_distribution"]["p1-a"]["source"] == "jikai"
    assert summary["preference_distribution"] == {
        "sample_a": 1,
        "sample_b": 1,
        "tie": 2,
    }
    assert summary["failure_modes"]["shallow facts"] == 4
    assert (
        summary["inter_rater_agreement"]["issue_spotting_coverage"]["rated_items"] == 0
    )


def test_summarize_distinguishes_dry_run_mode(tmp_path):
    ratings = tmp_path / "ratings.csv"
    manifest = tmp_path / "manifest.json"
    _write_rows(
        ratings,
        [
            _row("p1", "p1-a", "r1"),
            _row("p1", "p1-a", "r2"),
        ],
    )
    manifest.write_text(
        json.dumps({"rubric_version": "1.0", "eval_mode": "dry-run", "packets": []}),
        encoding="utf-8",
    )

    summary = summarize(ratings, manifest_path=manifest, min_samples=1)

    assert summary["eval_mode"] == "dry-run"
    assert summary["publishable"] is False
    assert summary["claims_permitted"] == []
    assert summary["claims_blocked"] == [
        "dry-run eval mode cannot support external quality claims"
    ]


def test_summarize_reports_chance_adjusted_agreement(tmp_path):
    ratings = tmp_path / "ratings.csv"
    row_a = _row("p1", "p1-a", "r1")
    row_b = _row("p1", "p1-a", "r2")
    row_c = _row("p2", "p2-a", "r1")
    row_d = _row("p2", "p2-a", "r2")
    row_c["issue_spotting_coverage"] = "1"
    row_d["issue_spotting_coverage"] = "5"
    _write_rows(ratings, [row_a, row_b, row_c, row_d])

    summary = summarize(ratings, min_samples=2)
    agreement = summary["inter_rater_agreement"]["issue_spotting_coverage"]

    assert agreement["rated_items"] == 2
    assert agreement["pair_count"] == 2
    assert agreement["exact_match_rate"] == 0.5
    assert agreement["mean_abs_delta"] == 2.0
    assert agreement["krippendorff_alpha_interval"] == 0.0


def test_empty_sheet_fails_fast(tmp_path):
    ratings = tmp_path / "ratings.csv"
    _write_rows(ratings, [])

    with pytest.raises(ValueError, match="no rating rows"):
        summarize(ratings)


def test_require_publishable_needs_min_samples_and_two_raters_per_item(tmp_path):
    ratings = tmp_path / "ratings.csv"
    _write_rows(ratings, [_row("p1", "p1-a", "r1")])

    with pytest.raises(ValueError, match="30 held-out"):
        summarize(ratings, require_publishable=True)

    with pytest.raises(ValueError, match="2 distinct raters per item"):
        summarize(ratings, require_publishable=True, min_samples=1)


def test_require_publishable_rejects_non_law_trained_profile(tmp_path):
    ratings = tmp_path / "ratings.csv"
    row_a = _row("p1", "p1-a", "r1")
    row_b = _row("p1", "p1-a", "r2")
    row_b["rater_profile"] = "friend"
    _write_rows(ratings, [row_a, row_b])

    with pytest.raises(ValueError, match="law-trained rater profiles"):
        summarize(ratings, require_publishable=True, min_samples=1)


def test_markdown_writer_outputs_required_sections(tmp_path):
    md = tmp_path / "summary.md"
    write_markdown(
        {
            "rubric_version": "1.0",
            "eval_mode": "external-human",
            "sample_size": 1,
            "rater_count": 3,
            "publishable": True,
            "min_samples_required": 1,
            "min_raters_per_item_required": 2,
            "publishability_errors": [],
            "rater_profiles": {"law_graduate": 3},
            "inter_rater_agreement": {
                "issue_spotting_coverage": {
                    "rated_items": 1,
                    "pair_count": 3,
                    "exact_match_rate": 1.0,
                    "mean_abs_delta": 0.0,
                    "krippendorff_alpha_interval": 1.0,
                }
            },
            "weighted_score_distribution": {
                "p1-a": {"source": "jikai", "mean": 90, "min": 85, "max": 95, "n": 3}
            },
            "preference_distribution": {"sample_a": 2},
            "failure_modes": {},
        },
        md,
    )

    text = md.read_text(encoding="utf-8")
    assert "## Publishability Gates" in text
    assert "Eval mode: external-human" in text
    assert "## Inter-Rater Agreement" in text
    assert "| issue_spotting_coverage | 1 | 3 | 1.0 | 0.0 | 1.0 |" in text
    assert "## Weighted Scores" in text
    assert "| p1-a | jikai | 90 | 85 | 95 | 3 |" in text
