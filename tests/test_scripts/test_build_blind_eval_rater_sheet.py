import csv
import json

import pytest

from script.build_blind_eval_rater_sheet import build_rater_sheet
from script.summarize_blind_eval_results import EXPECTED_HEADERS


def _manifest(tmp_path):
    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps(
            {
                "rubric_version": "1.0",
                "eval_mode": "external-human",
                "packets": [
                    {
                        "packet_id": "pilot0-001",
                        "samples": [
                            {"sample_id": "pilot0-001-a"},
                            {"sample_id": "pilot0-001-b"},
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def _rows(path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_build_rater_sheet_creates_sample_rows_per_rater(tmp_path):
    output = tmp_path / "ratings.csv"

    build_rater_sheet(
        _manifest(tmp_path),
        output_path=output,
        raw_raters=["r1:law_graduate", "r2:law_student_2l"],
    )

    rows = _rows(output)

    assert rows
    assert list(rows[0]) == EXPECTED_HEADERS
    assert len(rows) == 4
    assert {row["rater_id"] for row in rows} == {"r1", "r2"}
    assert {row["sample_id"] for row in rows} == {"pilot0-001-a", "pilot0-001-b"}
    assert all(row["issue_spotting_coverage"] == "" for row in rows)
    assert all(row["overall_preference"] == "" for row in rows)


def test_build_rater_sheet_rejects_duplicate_rater_ids(tmp_path):
    with pytest.raises(ValueError, match="duplicate rater_id"):
        build_rater_sheet(
            _manifest(tmp_path),
            output_path=tmp_path / "ratings.csv",
            raw_raters=["r1:law_graduate", "r1:lawyer"],
        )


def test_build_rater_sheet_rejects_unknown_profile(tmp_path):
    with pytest.raises(ValueError, match="unknown law-trained"):
        build_rater_sheet(
            _manifest(tmp_path),
            output_path=tmp_path / "ratings.csv",
            raw_raters=["r1:friend"],
        )


def test_build_rater_sheet_requires_two_samples_per_packet(tmp_path):
    manifest = _manifest(tmp_path)
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["packets"][0]["samples"] = [{"sample_id": "pilot0-001-a"}]
    manifest.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ValueError, match="exactly two samples"):
        build_rater_sheet(
            manifest,
            output_path=tmp_path / "ratings.csv",
            raw_raters=["r1:law_graduate"],
        )
