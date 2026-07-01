from pathlib import Path

from script.validate_blind_eval_artifact import (
    EXPECTED_RATER_HEADERS,
    validate_eval_artifacts,
    validate_rater_sheet,
    validate_sample_manifest_template,
)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_current_blind_eval_artifacts_validate():
    assert validate_eval_artifacts(repo_root()) == []


def test_rater_sheet_header_mismatch_is_reported(tmp_path):
    path = tmp_path / "ratings.csv"
    path.write_text("packet_id,sample_id\n", encoding="utf-8")

    assert validate_rater_sheet(path) == [f"{path} header mismatch"]


def test_rater_sheet_accepts_expected_header(tmp_path):
    path = tmp_path / "ratings.csv"
    path.write_text(",".join(EXPECTED_RATER_HEADERS) + "\n", encoding="utf-8")

    assert validate_rater_sheet(path) == []


def test_manifest_template_requires_hidden_source_labels(tmp_path):
    path = tmp_path / "manifest.json"
    path.write_text(
        """
{
  "schema_version": "1.0",
  "rubric_version": "1.0",
  "jurisdiction": "sg",
  "subject": "tort",
  "corpus_pack_key": "sg_tort",
  "corpus_pack_revision": "abc123",
  "packet_randomization": {
    "source_labels_visible_to_raters": true
  },
  "baseline": {
    "notes": "Do not use Quimbee or Studicata sample text without written permission."
  },
  "packets": [{}]
}
""".strip(),
        encoding="utf-8",
    )

    assert validate_sample_manifest_template(path) == [
        "packet_randomization.source_labels_visible_to_raters must be false"
    ]
