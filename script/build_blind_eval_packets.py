"""Build blinded rating packets from a blind-eval sample manifest."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _read_manifest(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("manifest root must be an object")
    return data


def _repo_path(repo_root: Path, raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return repo_root / path


def _sample_text(repo_root: Path, sample: dict[str, Any]) -> str:
    path = _repo_path(repo_root, str(sample.get("artifact_path", "")))
    if not path.exists():
        raise ValueError(f"missing sample artifact: {path}")
    return path.read_text(encoding="utf-8").strip()


def _packet_markdown(
    packet: dict[str, Any], *, repo_root: Path, rubric_version: str
) -> str:
    packet_id = str(packet.get("packet_id", "")).strip()
    if not packet_id:
        raise ValueError("packet_id is required")
    samples = packet.get("samples")
    if not isinstance(samples, list) or len(samples) != 2:
        raise ValueError(f"{packet_id}: exactly two samples required")

    lines = [
        f"# Blind Evaluation Packet {packet_id}",
        "",
        f"Rubric version: {rubric_version}",
        f"Topic: {packet.get('topic', '')}",
        f"Subtopics: {', '.join(packet.get('subtopics', []) or [])}",
        f"Difficulty: {packet.get('difficulty', '')}",
        "",
        "Rate each sample independently using the rubric. Do not infer origin from style.",
        "",
    ]
    for sample in samples:
        visible_label = str(sample.get("visible_label", "")).strip()
        sample_id = str(sample.get("sample_id", "")).strip()
        if not visible_label or not sample_id:
            raise ValueError(f"{packet_id}: sample_id and visible_label required")
        lines.extend(
            [
                f"## Sample {visible_label}",
                "",
                f"Sample ID: `{sample_id}`",
                "",
                _sample_text(repo_root, sample),
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def build_packets(
    manifest_path: Path,
    *,
    output_dir: Path,
    repo_root: Path = Path("."),
) -> list[Path]:
    manifest = _read_manifest(manifest_path)
    packets = manifest.get("packets")
    if not isinstance(packets, list) or not packets:
        raise ValueError("manifest.packets must be a non-empty array")
    output_dir.mkdir(parents=True, exist_ok=True)
    rubric_version = str(manifest.get("rubric_version", "1.0"))
    written: list[Path] = []
    for packet in packets:
        packet_id = str(packet.get("packet_id", "")).strip()
        if not packet_id:
            raise ValueError("packet_id is required")
        path = output_dir / f"{packet_id}.md"
        path.write_text(
            _packet_markdown(
                packet, repo_root=repo_root, rubric_version=rubric_version
            ),
            encoding="utf-8",
        )
        written.append(path)
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    args = parser.parse_args()
    try:
        written = build_packets(
            args.manifest,
            output_dir=args.output_dir,
            repo_root=args.repo_root,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    for path in written:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
