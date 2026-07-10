import json
from pathlib import Path

import pytest

from script.build_blind_eval_packets import build_packets


def test_build_packets_hides_sources(tmp_path: Path):
    samples = tmp_path / "samples"
    samples.mkdir()
    (samples / "jikai.md").write_text("First sample text", encoding="utf-8")
    (samples / "baseline.md").write_text("Second sample text", encoding="utf-8")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "rubric_version": "1.0",
                "packets": [
                    {
                        "packet_id": "pilot0-001",
                        "topic": "negligence",
                        "subtopics": ["duty_of_care"],
                        "difficulty": "medium",
                        "samples": [
                            {
                                "sample_id": "pilot0-001-a",
                                "visible_label": "A",
                                "source": "jikai",
                                "artifact_path": str(samples / "jikai.md"),
                            },
                            {
                                "sample_id": "pilot0-001-b",
                                "visible_label": "B",
                                "source": "baseline",
                                "artifact_path": str(samples / "baseline.md"),
                            },
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    written = build_packets(manifest, output_dir=tmp_path / "packets")

    assert len(written) == 1
    packet = written[0].read_text(encoding="utf-8")
    assert "Sample A" in packet
    assert "Sample B" in packet
    assert "First sample text" in packet
    assert "Second sample text" in packet
    assert "source" not in packet.lower()
    assert "jikai" not in packet.lower()
    assert "baseline" not in packet.lower()


def test_build_packets_requires_two_samples(tmp_path: Path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps({"packets": [{"packet_id": "p1", "samples": []}]}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="exactly two samples"):
        build_packets(manifest, output_dir=tmp_path / "packets")
