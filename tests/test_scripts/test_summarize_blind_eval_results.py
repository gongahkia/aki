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
        "doctrinal_accuracy": "5",
        "factual_richness": "4",
        "issue_coverage": "5",
        "explanation_quality": "4",
        "difficulty_calibration": "3",
        "usefulness_for_study": "5",
        "jurisdiction_fit": "5",
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

    summary = summarize(ratings, manifest_path=manifest, require_publishable=True)

    assert summary["sample_size"] == 2
    assert summary["rater_count"] == 3
    assert summary["publishable"] is True
    assert summary["weighted_score_distribution"]["p1-a"]["source"] == "jikai"
    assert summary["preference_distribution"] == {
        "sample_a": 1,
        "sample_b": 1,
        "tie": 1,
    }
    assert summary["failure_modes"]["shallow facts"] == 3


def test_empty_sheet_fails_fast(tmp_path):
    ratings = tmp_path / "ratings.csv"
    _write_rows(ratings, [])

    with pytest.raises(ValueError, match="no rating rows"):
        summarize(ratings)


def test_require_publishable_needs_three_raters(tmp_path):
    ratings = tmp_path / "ratings.csv"
    _write_rows(ratings, [_row("p1", "p1-a", "r1")])

    with pytest.raises(ValueError, match="3 distinct raters"):
        summarize(ratings, require_publishable=True)


def test_markdown_writer_outputs_required_sections(tmp_path):
    md = tmp_path / "summary.md"
    write_markdown(
        {
            "rubric_version": "1.0",
            "sample_size": 1,
            "rater_count": 3,
            "publishable": True,
            "rater_profiles": {"law_graduate": 3},
            "weighted_score_distribution": {
                "p1-a": {"source": "jikai", "mean": 90, "min": 85, "max": 95, "n": 3}
            },
            "preference_distribution": {"sample_a": 2},
            "failure_modes": {},
        },
        md,
    )

    text = md.read_text(encoding="utf-8")
    assert "## Weighted Scores" in text
    assert "| p1-a | jikai | 90 | 85 | 95 | 3 |" in text
