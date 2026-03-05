"""Interactive CLI tool for labelling corpus entries."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set

CORPUS_PATH = Path("corpus/clean/tort/corpus.json")
OUTPUT_PATH = Path("corpus/labelled/tort_labels.csv")
CSV_COLUMNS = [
    "id",
    "text",
    "topics",
    "complexity",
    "quality_score",
    "structural_elements",
    "num_parties",
    "case_references",
]
STRUCTURAL_OPTIONS = [
    "parties",
    "scenario",
    "legal_issues",
    "analysis",
    "complications",
    "defences",
    "remedies",
    "timeline",
]


def _load_corpus() -> List[Dict]:
    if not CORPUS_PATH.exists():
        print(f"error: corpus not found at {CORPUS_PATH}")
        sys.exit(1)
    with open(CORPUS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_labelled_ids() -> Set[str]:
    """Return IDs already labelled in the output CSV."""
    if not OUTPUT_PATH.exists():
        return set()
    ids = set()
    with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ids.add(row.get("id", ""))
    return ids


def _get_topic_suggestions(text: str) -> Optional[List[str]]:
    """Try to get topic predictions from trained classifier."""
    try:
        from .pipeline import MLPipeline

        pipeline = MLPipeline()
        pipeline.load_all()
        if not pipeline.classifier.is_trained:
            return None
        prediction = pipeline.predict(text)
        return prediction.get("topics", [])
    except Exception:
        return None


def _get_canonical_topics() -> List[str]:
    from ..domain.topics import TORT_TOPICS

    return list(TORT_TOPICS.keys())


def _prompt(msg: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    val = input(f"{msg}{suffix}: ").strip()
    return val if val else default


def _prompt_topics(existing_topics: List[str], suggestions: Optional[List[str]]) -> str:
    canonical = _get_canonical_topics()
    print(f"\n  available topics: {', '.join(canonical)}")
    if existing_topics:
        print(f"  corpus topics:    {', '.join(existing_topics)}")
    if suggestions:
        print(f"  ML suggestions:   {', '.join(suggestions)}")
    default = "|".join(existing_topics) if existing_topics else ""
    while True:
        raw = _prompt("  topics (pipe-separated)", default)
        if not raw:
            print("  error: at least one topic required")
            continue
        return raw


def _prompt_complexity() -> int:
    while True:
        raw = _prompt("  complexity (1-5)", "3")
        try:
            val = int(raw)
            if 1 <= val <= 5:
                return val
        except ValueError:
            pass
        print("  error: must be integer 1-5")


def _prompt_quality() -> float:
    while True:
        raw = _prompt("  quality_score (0.0-1.0)", "0.7")
        try:
            val = float(raw)
            if 0.0 <= val <= 1.0:
                return val
        except ValueError:
            pass
        print("  error: must be float 0.0-1.0")


def _prompt_structural() -> str:
    print(f"  structural options: {', '.join(STRUCTURAL_OPTIONS)}")
    raw = _prompt(
        "  structural_elements (pipe-separated)", "parties|scenario|legal_issues"
    )
    return raw


def _prompt_num_parties() -> int:
    while True:
        raw = _prompt("  num_parties", "3")
        try:
            val = int(raw)
            if val >= 1:
                return val
        except ValueError:
            pass
        print("  error: must be positive integer")


def _write_row(row: Dict):
    """Append a single row to the CSV, creating headers if needed."""
    write_header = not OUTPUT_PATH.exists() or OUTPUT_PATH.stat().st_size == 0
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        if write_header:
            writer.writeheader()
        writer.writerow(row)


def main():
    corpus = _load_corpus()
    labelled_ids = _load_labelled_ids()
    total = len(corpus)
    remaining = [
        (i, entry) for i, entry in enumerate(corpus) if str(i) not in labelled_ids
    ]
    if not remaining:
        print(f"all {total} entries already labelled")
        return
    print(f"labeller: {len(remaining)}/{total} entries remaining (resume-aware)")
    print("press Ctrl+C to stop at any time\n")
    for idx, entry in remaining:
        entry_id = str(idx)
        text = entry.get("text", "")
        existing_topics = entry.get("topic", entry.get("topics", []))
        if isinstance(existing_topics, str):
            existing_topics = [existing_topics]
        print(f"{'='*60}")
        print(f"entry {entry_id}/{total-1}")
        preview = text[:500] + ("..." if len(text) > 500 else "")
        print(f"\n{preview}\n")
        suggestions = _get_topic_suggestions(text)
        try:
            topics = _prompt_topics(existing_topics, suggestions)
            complexity = _prompt_complexity()
            quality = _prompt_quality()
            structural = _prompt_structural()
            num_parties = _prompt_num_parties()
            case_refs = _prompt("  case_references (pipe-separated, optional)", "")
        except (KeyboardInterrupt, EOFError):
            print("\nstopped")
            return
        row = {
            "id": entry_id,
            "text": text,
            "topics": topics,
            "complexity": complexity,
            "quality_score": quality,
            "structural_elements": structural,
            "num_parties": num_parties,
            "case_references": case_refs,
        }
        _write_row(row)
        print(f"  -> saved entry {entry_id}\n")
    print(f"\ndone — all {total} entries labelled")


if __name__ == "__main__":
    main()
