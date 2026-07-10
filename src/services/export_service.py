"""Export service: convert generations to various formats (Anki, CSV, etc.)."""

from __future__ import annotations

import csv
import html
import json
from pathlib import Path
from typing import Any, Dict, List

import structlog

logger = structlog.get_logger(__name__)


def format_practice_artifact(practice: Dict[str, Any]) -> List[str]:
    if not isinstance(practice, dict) or not practice:
        return []
    lines = [f"Practice mode: {practice.get('mode', 'issue_spotting')}"]
    if practice.get("answer_visibility"):
        lines.append(f"Answer visibility: {practice['answer_visibility']}")
    checklist = practice.get("issue_checklist") or []
    if checklist:
        lines.append("Issue checklist:")
        for item in checklist:
            label = item.get("label") or item.get("topic") or "issue"
            task = item.get("student_task") or item.get("expected_analysis") or ""
            lines.append(f"- {label}: {task}")
    rubric = practice.get("rubric") or []
    if rubric:
        lines.append("Rubric:")
        for item in rubric:
            criterion = item.get("criterion", "criterion")
            points = item.get("points", "")
            description = item.get("description", "")
            lines.append(f"- {criterion} ({points} pts): {description}")
    hints = practice.get("hints") or []
    if hints:
        lines.append("Progressive hints:")
        for item in hints:
            lines.append(f"- hint {item.get('level', '?')}: {item.get('text', '')}")
    timer = practice.get("timer") or {}
    if timer:
        lines.append(f"Timer: {timer.get('seconds')} seconds")
    return lines


def export_to_anki_tsv(
    generations: List[Dict[str, Any]],
    output_path: str,
    include_model_answer: bool = True,
) -> int:
    """Export hypotheticals as Anki-compatible TSV (tab-separated).
    Front: fact pattern. Back: model answer + topic tags.
    Returns number of cards exported."""
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter="\t", quoting=csv.QUOTE_MINIMAL)
        for gen in generations:
            hypo = gen.get("hypothetical", "").strip()
            if not hypo:
                continue
            front = html.escape(hypo).replace("\n", "<br>")
            back_parts = []
            if include_model_answer:
                model_answer = gen.get("model_answer", "").strip()
                if model_answer:
                    back_parts.append(html.escape(model_answer).replace("\n", "<br>"))
            analysis = gen.get("analysis", "").strip()
            if analysis and not back_parts:
                back_parts.append(html.escape(analysis).replace("\n", "<br>"))
            topics = gen.get("topics", [])
            if isinstance(topics, str):
                topics = [topics]
            tags = " ".join(f"tort::{t}" for t in topics)
            practice = gen.get("practice") or gen.get("metadata", {}).get("practice", {})
            practice_lines = format_practice_artifact(practice)
            if practice_lines:
                back_parts.append(
                    html.escape("\n".join(practice_lines)).replace("\n", "<br>")
                )
            back = "<hr>".join(back_parts) if back_parts else "(no model answer)"
            writer.writerow([front, back, tags])
            count += 1
    logger.info("exported anki cards", count=count, path=str(out))
    return count


def export_to_csv(
    generations: List[Dict[str, Any]],
    output_path: str,
) -> int:
    """Export hypotheticals as flat CSV."""
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "id",
        "topics",
        "hypothetical",
        "analysis",
        "model_answer",
        "practice_mode",
        "issue_checklist",
        "rubric",
        "quality_score",
    ]
    count = 0
    with out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for gen in generations:
            topics = gen.get("topics", [])
            practice = gen.get("practice") or gen.get("metadata", {}).get("practice", {})
            writer.writerow(
                {
                    "id": gen.get("id", ""),
                    "topics": (
                        "|".join(topics) if isinstance(topics, list) else str(topics)
                    ),
                    "hypothetical": gen.get("hypothetical", ""),
                    "analysis": gen.get("analysis", ""),
                    "model_answer": gen.get("model_answer", ""),
                    "practice_mode": practice.get("mode", ""),
                    "issue_checklist": json.dumps(
                        practice.get("issue_checklist", [])
                    ),
                    "rubric": json.dumps(practice.get("rubric", [])),
                    "quality_score": gen.get("quality_score", ""),
                }
            )
            count += 1
    logger.info("exported csv", count=count, path=str(out))
    return count
