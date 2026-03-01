"""Seeded textual demo-flow smoke test for generation/report/export artifacts."""

import asyncio
from pathlib import Path

from src.tui import app_runner
from src.tui.services.stream_persistence import persist_stream_generation


def test_textual_demo_flow_smoke_generates_artifacts(monkeypatch, tmp_path: Path):
    artifacts_dir = tmp_path / "demo_artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    class FakeTextualApp:
        def run(self):
            generation_id = asyncio.run(
                persist_stream_generation(
                    topic="negligence",
                    provider="ollama",
                    model="llama3",
                    complexity=3,
                    parties=2,
                    method="pure_llm",
                    temperature=0.0,
                    red_herrings=False,
                    hypothetical="Seeded textual demo hypothetical output.",
                    validation_results={"passed": True, "quality_score": 8.0},
                    correlation_id="seeded-demo-424242",
                    include_analysis=False,
                    partial_snapshot=False,
                    cancellation_metadata={"seed": 424242},
                )
            )

            from src.services.workflow_facade import workflow_facade

            report_id = asyncio.run(
                workflow_facade.save_generation_report(
                    generation_id=generation_id,
                    issue_types=["demo_smoke"],
                    comment="seeded smoke report",
                )
            )

            export_path = artifacts_dir / f"export_{generation_id}.txt"
            export_path.write_text(
                "Seeded textual demo export artifact", encoding="utf-8"
            )

            (artifacts_dir / "generation_id.txt").write_text(
                str(generation_id), encoding="utf-8"
            )
            (artifacts_dir / "report_id.txt").write_text(
                str(report_id), encoding="utf-8"
            )

    monkeypatch.setattr("src.tui.textual_app.JikaiTextualApp", FakeTextualApp)

    app_runner.run("tui-only", ui="textual")

    generation_marker = artifacts_dir / "generation_id.txt"
    report_marker = artifacts_dir / "report_id.txt"
    export_artifact = list(artifacts_dir.glob("export_*.txt"))

    assert generation_marker.exists()
    assert report_marker.exists()
    assert export_artifact
