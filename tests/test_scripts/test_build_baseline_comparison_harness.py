import json
from pathlib import Path

import pytest

from script.build_baseline_comparison_harness import build_harness


def _artifact(path: Path, text: str) -> str:
    path.write_text(text, encoding="utf-8")
    return str(path)


def _config(tmp_path: Path, *, eval_mode: str = "dry-run") -> Path:
    samples = tmp_path / "samples"
    samples.mkdir()
    config = tmp_path / "config.json"
    config.write_text(
        json.dumps(
            {
                "schema_version": "jikai.baseline_comparison.config.v1",
                "eval_mode": eval_mode,
                "rubric_version": "1.0",
                "jurisdiction": "sg",
                "subject": "tort",
                "corpus_pack_key": "sg_tort",
                "corpus_pack_revision": "abc123",
                "packet_prefix": "cmp",
                "random_seed": 7,
                "items": [
                    {
                        "item_id": "negligence-001",
                        "topic": "negligence",
                        "subtopics": ["duty_of_care"],
                        "difficulty": "medium",
                        "samples": [
                            {
                                "source_type": "jikai_generated_hypo",
                                "artifact_path": _artifact(
                                    samples / "jikai.md", "Alpha sample text."
                                ),
                            },
                            {
                                "source_type": "repo_fixture_hypo",
                                "artifact_path": _artifact(
                                    samples / "fixture.md", "Beta sample text."
                                ),
                            },
                            {
                                "source_type": "generic_llm_prompt_output",
                                "artifact_path": _artifact(
                                    samples / "llm.md", "Gamma sample text."
                                ),
                            },
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return config


def test_build_harness_creates_pairwise_blinded_packets(tmp_path: Path):
    paths = build_harness(_config(tmp_path), output_dir=tmp_path / "out")

    manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
    source_map = json.loads(paths["source_map"].read_text(encoding="utf-8"))
    packets = sorted(paths["packet_dir"].glob("*.md"))

    assert manifest["eval_mode"] == "dry-run"
    assert manifest["metrics"] == [
        "student_utility",
        "legal_accuracy",
        "issue_density",
        "novelty",
        "answer_helpfulness",
    ]
    assert len(manifest["packets"]) == 2
    assert len(packets) == 2
    assert source_map["samples"]

    packet_text = "\n".join(path.read_text(encoding="utf-8") for path in packets)
    assert "Alpha sample text." in packet_text
    assert "Beta sample text." in packet_text
    assert "Gamma sample text." in packet_text
    assert "jikai_generated_hypo" not in packet_text
    assert "repo_fixture_hypo" not in packet_text
    assert "generic_llm_prompt_output" not in packet_text
    assert "source" not in packet_text.lower()


def test_harness_records_eval_mode_policy(tmp_path: Path):
    paths = build_harness(
        _config(tmp_path, eval_mode="external-human"), output_dir=tmp_path / "out"
    )

    manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))

    assert manifest["eval_mode"] == "external-human"
    assert manifest["mode_policy"]["human_raters"] == "required"


def test_harness_includes_cleared_external_baseline(tmp_path: Path):
    config = _config(tmp_path)
    data = json.loads(config.read_text(encoding="utf-8"))
    samples = Path(data["items"][0]["samples"][1]["artifact_path"]).parent
    data["items"][0]["samples"].append(
        {
            "source_type": "licensed_external_hypo",
            "artifact_path": _artifact(samples / "external.md", "Delta sample text."),
            "license_status": "permission_granted",
            "permission_evidence": "ticket-123",
        }
    )
    config.write_text(json.dumps(data), encoding="utf-8")

    paths = build_harness(config, output_dir=tmp_path / "out")
    manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))

    assert len(manifest["packets"]) == 3
    assert "licensed_external_hypo" in manifest["comparison_sources"]


def test_harness_blocks_uncleared_external_text(tmp_path: Path):
    config = _config(tmp_path)
    data = json.loads(config.read_text(encoding="utf-8"))
    data["items"][0]["samples"].append(
        {
            "source_type": "licensed_external_hypo",
            "artifact_path": data["items"][0]["samples"][1]["artifact_path"],
            "license_status": "permission-required",
        }
    )
    config.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ValueError, match="licensed_external_hypo requires cleared"):
        build_harness(config, output_dir=tmp_path / "out")
