"""Build blinded baseline-comparison packets from source-bucket artifacts."""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Any

from script.build_blind_eval_packets import build_packets

EVAL_MODES = {"dry-run", "internal", "external-human"}
SOURCE_TYPES = {
    "jikai_generated_hypo",
    "repo_fixture_hypo",
    "licensed_external_hypo",
    "generic_llm_prompt_output",
}
BASELINE_SOURCE_TYPES = SOURCE_TYPES - {"jikai_generated_hypo"}
CLEARED_EXTERNAL_STATUSES = {
    "permission_granted",
    "open_license",
    "public_domain",
}
METRICS = [
    "student_utility",
    "legal_accuracy",
    "issue_density",
    "novelty",
    "answer_helpfulness",
]
MODE_POLICIES = {
    "dry-run": {
        "human_raters": "not_required",
        "claims_permitted": [],
        "claims_blocked": ["external quality claims"],
    },
    "internal": {
        "human_raters": "internal_allowed",
        "claims_permitted": [],
        "claims_blocked": ["external quality claims"],
    },
    "external-human": {
        "human_raters": "required",
        "claims_permitted": ["only after rating summary passes publishability gates"],
        "claims_blocked": [],
    },
}


def _read_config(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("config root must be an object")
    return data


def _repo_path(repo_root: Path, raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return repo_root / path


def _require_str(data: dict[str, Any], key: str) -> str:
    value = str(data.get(key, "")).strip()
    if not value:
        raise ValueError(f"{key} is required")
    return value


def _source_type(sample: dict[str, Any]) -> str:
    source_type = _require_str(sample, "source_type")
    if source_type not in SOURCE_TYPES:
        raise ValueError(f"unknown source_type: {source_type}")
    return source_type


def _check_sample(sample: dict[str, Any], *, repo_root: Path) -> None:
    source_type = _source_type(sample)
    artifact_path = _repo_path(repo_root, _require_str(sample, "artifact_path"))
    if not artifact_path.exists():
        raise ValueError(f"missing sample artifact: {artifact_path}")
    if source_type != "licensed_external_hypo":
        return
    license_status = str(sample.get("license_status", "")).strip()
    if license_status not in CLEARED_EXTERNAL_STATUSES:
        raise ValueError(
            "licensed_external_hypo requires cleared license_status: "
            + ", ".join(sorted(CLEARED_EXTERNAL_STATUSES))
        )
    if not str(sample.get("permission_evidence", "")).strip():
        raise ValueError("licensed_external_hypo requires permission_evidence")


def _mode(config: dict[str, Any]) -> str:
    eval_mode = str(config.get("eval_mode", "")).strip()
    if eval_mode not in EVAL_MODES:
        raise ValueError("eval_mode must be dry-run, internal, or external-human")
    return eval_mode


def _item_samples(item: dict[str, Any], *, repo_root: Path) -> list[dict[str, Any]]:
    samples = item.get("samples")
    if not isinstance(samples, list) or not samples:
        raise ValueError("item.samples must be a non-empty array")
    checked: list[dict[str, Any]] = []
    for sample in samples:
        if not isinstance(sample, dict):
            raise ValueError("each sample must be an object")
        _check_sample(sample, repo_root=repo_root)
        checked.append(sample)
    jikai = [
        sample for sample in checked if _source_type(sample) == "jikai_generated_hypo"
    ]
    baselines = [
        sample for sample in checked if _source_type(sample) in BASELINE_SOURCE_TYPES
    ]
    if len(jikai) != 1:
        raise ValueError("each item requires exactly one jikai_generated_hypo sample")
    if not baselines:
        raise ValueError("each item requires at least one baseline sample")
    return checked


def _packet_samples(
    packet_id: str,
    pair: list[dict[str, Any]],
    *,
    rng: random.Random,
) -> list[dict[str, Any]]:
    shuffled = list(pair)
    rng.shuffle(shuffled)
    samples: list[dict[str, Any]] = []
    for index, sample in enumerate(shuffled):
        visible_label = chr(ord("A") + index)
        samples.append(
            {
                "sample_id": f"{packet_id}-{visible_label.lower()}",
                "visible_label": visible_label,
                "source": _source_type(sample),
                "artifact_path": _require_str(sample, "artifact_path"),
            }
        )
    return samples


def build_harness(
    config_path: Path,
    *,
    output_dir: Path,
    repo_root: Path = Path("."),
) -> dict[str, Path]:
    config = _read_config(config_path)
    eval_mode = _mode(config)
    items = config.get("items")
    if not isinstance(items, list) or not items:
        raise ValueError("items must be a non-empty array")
    seed = int(config.get("random_seed", 20260710))
    rng = random.Random(seed)
    packet_prefix = str(config.get("packet_prefix", eval_mode)).strip() or eval_mode
    packets: list[dict[str, Any]] = []
    source_map: dict[str, Any] = {
        "schema_version": "jikai.baseline_comparison.source_map.v1",
        "eval_mode": eval_mode,
        "samples": {},
    }

    for item_index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            raise ValueError("each item must be an object")
        samples = _item_samples(item, repo_root=repo_root)
        jikai = next(
            sample
            for sample in samples
            if _source_type(sample) == "jikai_generated_hypo"
        )
        baselines = [
            sample
            for sample in samples
            if _source_type(sample) in BASELINE_SOURCE_TYPES
        ]
        for baseline_index, baseline in enumerate(baselines, start=1):
            packet_id = f"{packet_prefix}-{item_index:03d}-{baseline_index:02d}"
            packet_samples = _packet_samples(packet_id, [jikai, baseline], rng=rng)
            packets.append(
                {
                    "packet_id": packet_id,
                    "topic": str(item.get("topic", "")),
                    "subtopics": item.get("subtopics", []),
                    "difficulty": str(item.get("difficulty", "")),
                    "samples": packet_samples,
                }
            )
            for packet_sample in packet_samples:
                original = (
                    jikai
                    if packet_sample["source"] == _source_type(jikai)
                    else baseline
                )
                source_map["samples"][packet_sample["sample_id"]] = {
                    "packet_id": packet_id,
                    "item_id": str(item.get("item_id", "")),
                    "source_type": _source_type(original),
                    "artifact_path": _require_str(original, "artifact_path"),
                    "license_status": str(original.get("license_status", "")),
                    "permission_evidence": str(original.get("permission_evidence", "")),
                }

    output_dir.mkdir(parents=True, exist_ok=True)
    packet_dir = output_dir / "packets"
    manifest = {
        "schema_version": "jikai.baseline_comparison.manifest.v1",
        "rubric_version": str(config.get("rubric_version", "1.0")),
        "eval_mode": eval_mode,
        "mode_policy": MODE_POLICIES[eval_mode],
        "jurisdiction": str(config.get("jurisdiction", "sg")),
        "subject": str(config.get("subject", "tort")),
        "corpus_pack_key": str(config.get("corpus_pack_key", "sg_tort")),
        "corpus_pack_revision": str(config.get("corpus_pack_revision", "")),
        "metrics": METRICS,
        "packet_randomization": {
            "method": "seeded_pairwise_shuffle",
            "seed": seed,
            "source_labels_visible_to_raters": False,
        },
        "comparison_sources": sorted(
            {_source_type(sample) for item in items for sample in item["samples"]}
        ),
        "packets": packets,
    }
    manifest_path = output_dir / "manifest.json"
    source_map_path = output_dir / "private_source_map.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    source_map_path.write_text(
        json.dumps(source_map, indent=2) + "\n", encoding="utf-8"
    )
    build_packets(manifest_path, output_dir=packet_dir, repo_root=repo_root)
    return {
        "manifest": manifest_path,
        "source_map": source_map_path,
        "packet_dir": packet_dir,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    args = parser.parse_args()
    try:
        paths = build_harness(
            args.config,
            output_dir=args.output_dir,
            repo_root=args.repo_root,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    for path in paths.values():
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
