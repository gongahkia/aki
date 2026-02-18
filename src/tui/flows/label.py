"""Corpus labeling flow."""

import csv
import json
from pathlib import Path

from rich import box
from rich.panel import Panel
from questionary import Choice

from src.tui.console import console, tlog
from src.tui.inputs import (
    _path,
    _select_quit,
    _checkbox,
    _validated_text,
    _validate_number,
    _confirm,
    _text,
    _topic_choices,
)


class LabelFlowMixin:
    """Mixin for labeling flows."""

    def label_flow(self):
        console.print("\n[bold yellow]Label Corpus → Training CSV[/bold yellow]")
        # Auto-use default corpus if it exists and has entries
        corpus_path = self._corpus_path
        if Path(corpus_path).exists():
            try:
                with open(corpus_path) as f:
                    data = json.load(f)
                entries = data if isinstance(data, list) else data.get("entries", [])
                if entries:
                    console.print(f"[dim]Using corpus: {corpus_path} ({len(entries)} entries)[/dim]")
                else:
                    corpus_path = _path("Corpus JSON to label", default=self._corpus_path)
                    if corpus_path is None:
                        return
            except Exception:
                corpus_path = _path("Corpus JSON to label", default=self._corpus_path)
                if corpus_path is None:
                    return
        else:
            corpus_path = _path("Corpus JSON to label", default=self._corpus_path)
            if corpus_path is None:
                return
        out_path = _path("Output labelled CSV", default=self._train_data)
        if out_path is None:
            return
        try:
            with open(corpus_path) as f:
                data = json.load(f)
            entries = data if isinstance(data, list) else data.get("entries", [])
        except Exception as e:
            console.print(f"[red]✗ Failed to load corpus: {e}[/red]")
            return
        if not entries:
            console.print("[red]✗ No entries in corpus[/red]")
            return
        existing = []
        skip_texts = set()
        if Path(out_path).exists():
            with open(out_path) as f:
                reader = csv.DictReader(f)
                for row in reader:
                    existing.append(row)
                    skip_texts.add(row.get("text", "")[:100])
            console.print(
                f"[dim]{len(existing)} already labelled, will append new[/dim]"
            )
        unlabelled = [e for e in entries if e.get("text", "")[:100] not in skip_texts]
        console.print(
            f"[cyan]{len(unlabelled)} entries to label ({len(entries)} total)[/cyan]"
        )
        if not unlabelled:
            console.print("[green]All entries already labelled[/green]")
            return
        difficulty_choices = [
            Choice("Easy", value="easy"),
            Choice("Medium", value="medium"),
            Choice("Hard", value="hard"),
        ]
        labelled = list(existing)
        count = 0
        for i, entry in enumerate(unlabelled):
            text = entry.get("text", "")
            topics_hint = entry.get("topic", entry.get("topics", ""))
            if isinstance(topics_hint, list):
                topics_hint = ", ".join(topics_hint)
            subtitle = f"Topics: {topics_hint}" if topics_hint else None
            panel = Panel(
                text,
                title=f"Entry {i+1}/{len(unlabelled)}",
                subtitle=subtitle,
                box=box.ROUNDED,
                border_style="cyan",
            )
            if len(text) > 1000:
                with console.pager(styles=True):
                    console.print(panel)
            else:
                console.print(panel)
            action = _select_quit(
                "Action",
                choices=[
                    Choice("Label this entry", value="label"),
                    Choice("Skip", value="skip"),
                    Choice("Save & quit", value="done"),
                ],
            )
            if action is None or action == "done":
                break
            if action == "skip":
                continue
            topics = _checkbox("Topics", choices=_topic_choices())
            if topics is None:
                break
            quality = _validated_text(
                "Quality score (0-10)",
                default="7.0",
                validate=_validate_number(0.0, 10.0, is_float=True),
            )
            if quality is None:
                break
            difficulty = _select_quit("Difficulty", choices=difficulty_choices)
            if difficulty is None:
                break
            labelled.append(
                {
                    "text": text,
                    "topic_labels": "|".join(topics),
                    "quality_score": quality,
                    "difficulty_level": difficulty,
                }
            )
            count += 1
            # Show confirmation with the label just assigned
            console.print(
                f"[green]✓ Labelled ({count} this session)[/green] "
                f"[dim]Topics: {', '.join(topics[:3])}{'...' if len(topics) > 3 else ''}, "
                f"Quality: {quality}, Difficulty: {difficulty}[/dim]"
            )
            # Offer to re-label
            if _confirm("Re-label this entry?", default=False):
                # Remove the last entry and redo
                labelled.pop()
                count -= 1
                # Re-prompt for labels
                topics = _checkbox("Topics", choices=_topic_choices())
                if topics is None:
                    break
                quality = _validated_text(
                    "Quality score (0-10)",
                    default="7.0",
                    validate=_validate_number(0.0, 10.0, is_float=True),
                )
                if quality is None:
                    break
                difficulty = _select_quit("Difficulty", choices=difficulty_choices)
                if difficulty is None:
                    break
                labelled.append(
                    {
                        "text": text,
                        "topic_labels": "|".join(topics),
                        "quality_score": quality,
                        "difficulty_level": difficulty,
                    }
                )
                count += 1
                console.print(
                    f"[green]✓ Re-labelled[/green] "
                    f"[dim]Topics: {', '.join(topics[:3])}, Quality: {quality}, Difficulty: {difficulty}[/dim]"
                )
        if count > 0:
            Path(out_path).parent.mkdir(parents=True, exist_ok=True)
            with open(out_path, "w", newline="") as f:
                w = csv.DictWriter(
                    f,
                    fieldnames=[
                        "text",
                        "topic_labels",
                        "quality_score",
                        "difficulty_level",
                    ],
                )
                w.writeheader()
                w.writerows(labelled)
            self._train_data = out_path
            console.print(f"[green]✓ Saved {len(labelled)} rows → {out_path}[/green]")
            tlog.info("LABEL  %d new, %d total → %s", count, len(labelled), out_path)
        else:
            console.print("[dim]No new labels added[/dim]")

    def bulk_label_flow(self):
        """Fast bulk labelling: show text, single-keystroke quality + difficulty, auto-advance."""
        console.print("\n[bold yellow]Bulk Label Corpus[/bold yellow]")
        console.print(
            "[dim]Fast labelling: rate quality (1-9) and difficulty (e/m/h) per entry.\n"
            "Press 'q' to save and quit. Labels auto-save in batches of 10.[/dim]\n"
        )
        corpus_path = _path("Corpus JSON to label", default=self._corpus_path)
        if corpus_path is None:
            return
        out_path = _path("Output labelled CSV", default=self._train_data)
        if out_path is None:
            return
        try:
            with open(corpus_path) as f:
                data = json.load(f)
            entries = data if isinstance(data, list) else data.get("entries", [])
        except Exception as e:
            console.print(f"[red]✗ Failed to load corpus: {e}[/red]")
            return
        if not entries:
            console.print("[red]✗ No entries[/red]")
            return

        existing = []
        skip_texts = set()
        if Path(out_path).exists():
            with open(out_path) as f:
                reader = csv.DictReader(f)
                for row in reader:
                    existing.append(row)
                    skip_texts.add(row.get("text", "")[:100])
        unlabelled = [e for e in entries if e.get("text", "")[:100] not in skip_texts]
        if not unlabelled:
            console.print("[green]All entries already labelled[/green]")
            return
        console.print(f"[cyan]{len(unlabelled)} entries to label[/cyan]")

        diff_map = {"e": "easy", "m": "medium", "h": "hard"}
        labelled = list(existing)
        count = 0

        for i, entry in enumerate(unlabelled):
            text = entry.get("text", "")
            topics_hint = entry.get("topic", entry.get("topics", ""))
            if isinstance(topics_hint, list):
                topics_hint = ", ".join(topics_hint)
            console.print(
                Panel(
                    text[:800] + ("..." if len(text) > 800 else ""),
                    title=f"[{i+1}/{len(unlabelled)}] Topics: {topics_hint}",
                    box=box.ROUNDED,
                    border_style="cyan",
                )
            )
            quality = _text("Quality (1-9, q to quit)", default="7")
            if quality is None or quality.lower() == "q":
                break
            try:
                q = int(quality)
                if q < 1 or q > 9:
                    console.print("[red]Must be 1-9[/red]")
                    continue
            except ValueError:
                console.print("[red]Must be a number 1-9[/red]")
                continue
            diff = _text("Difficulty (e/m/h)", default="m")
            if diff is None or diff.lower() == "q":
                break
            if diff.lower() not in diff_map:
                console.print("[red]Must be e, m, or h[/red]")
                continue
            labelled.append(
                {
                    "text": text,
                    "topic_labels": topics_hint
                    if isinstance(topics_hint, str)
                    else "|".join(topics_hint),
                    "quality_score": str(q),
                    "difficulty_level": diff_map[diff.lower()],
                }
            )
            count += 1
            console.print(f"[green]✓ {count} labelled[/green]")

            # Auto-save every 10
            if count % 10 == 0:
                self._write_labels(out_path, labelled)
                console.print(f"[dim]Auto-saved {len(labelled)} rows[/dim]")

        if count > 0:
            self._write_labels(out_path, labelled)
            console.print(f"[green]✓ Saved {len(labelled)} rows → {out_path}[/green]")
            tlog.info("BULK_LABEL  %d new, %d total", count, len(labelled))
        else:
            console.print("[dim]No new labels added[/dim]")

    def _write_labels(self, out_path, labelled):
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", newline="") as f:
            w = csv.DictWriter(
                f,
                fieldnames=[
                    "text",
                    "topic_labels",
                    "quality_score",
                    "difficulty_level",
                ],
            )
            w.writeheader()
            w.writerows(labelled)
