"""Corpus management flow."""

import csv
import json
import re
from pathlib import Path

from rich import box
from rich.panel import Panel
from rich.table import Table
from questionary import Choice

from src.tui.console import console, tlog
from src.tui.inputs import (
    _path,
    _confirm,
    _select_quit,
    _text,
    _checkbox,
    _topic_choices,
)
from src.tui.constants import IMPORT_MAP


class CorpusFlowMixin:
    """Mixin for corpus management flows."""

    def corpus_flow(self):
        console.print("\n[bold yellow]Browse Corpus[/bold yellow]")
        # Auto-use default corpus if it exists and has entries
        path = self._corpus_path
        if Path(path).exists():
            try:
                with open(path) as f:
                    data = json.load(f)
                entries = data if isinstance(data, list) else data.get("entries", [])
                if entries:
                    console.print(f"[dim]Using corpus: {path} ({len(entries)} entries)[/dim]")
                else:
                    path = _path("Corpus file path", default=self._corpus_path)
            except Exception:
                path = _path("Corpus file path", default=self._corpus_path)
        else:
            path = _path("Corpus file path", default=self._corpus_path)
        if path is None:
            return
        self._load_corpus(path)
        while True:
            c = _select_quit(
                "Corpus Menu",
                choices=[
                    Choice("View entry", value="1"),
                    Choice("Search", value="2"),
                    Choice("Filter by topic", value="3"),
                    Choice("Export CSV", value="4"),
                    Choice("Export JSON", value="5"),
                    Choice("Preprocess raw", value="6"),
                    Choice("Load different file", value="7"),
                ],
            )
            if c is None:
                return
            if c == "1":
                self._view_entry()
            elif c == "2":
                self._search_corpus()
            elif c == "3":
                self._filter_corpus()
            elif c == "4":
                self._export_corpus("csv")
            elif c == "5":
                self._export_corpus("json")
            elif c == "6":
                self._preprocess_raw()
            elif c == "7":
                path = _path(
                    "Corpus file path",
                    default=(self._loaded_path or self._corpus_path),
                )
                if path is not None:
                    self._load_corpus(path)

    def _load_corpus(self, path):
        try:
            p = Path(path)
            if not p.exists():
                console.print(f"[red]✗ File not found: {path}[/red]")
                return
            ext = p.suffix.lower()
            if ext == ".json":
                self._entries = self._parse_json(p)
            elif ext == ".csv":
                self._entries = self._parse_csv(p)
            elif ext == ".txt":
                self._entries = self._parse_txt(p)
            else:
                console.print(f"[red]✗ Unsupported type: {ext}[/red]")
                return
            self._loaded_path = path
            console.print(
                f"[green]✓ Loaded {len(self._entries)} entries from {p.name}[/green]"
            )
            self._display_entries(self._entries)
            tlog.info("CORPUS  loaded %d entries from %s", len(self._entries), path)
        except Exception as e:
            console.print(f"[red]✗ Load error: {e}[/red]")

    def _display_entries(self, entries, page=0, page_size=20):
        while True:
            start = page * page_size
            end = min(start + page_size, len(entries))
            if start >= len(entries):
                return
            table = Table(
                title=f"Entries [{start+1}-{end} of {len(entries)}]", box=box.ROUNDED
            )
            table.add_column("ID", style="cyan", width=5)
            table.add_column("Topics", style="yellow", width=20)
            table.add_column("Quality", style="yellow", width=8)
            table.add_column("Words", style="yellow", width=6)
            table.add_column("Preview", style="dim")
            for i in range(start, end):
                e = entries[i]
                text = e["text"]
                preview = (text[:60] + "...") if len(text) > 60 else text
                preview = preview.replace("\n", " ")
                table.add_row(
                    str(i),
                    e.get("topics", ""),
                    str(e.get("quality", "N/A")),
                    str(len(text.split())),
                    preview,
                )
            console.print(table)
            has_next = end < len(entries)
            has_prev = page > 0
            if not has_next and not has_prev:
                return
            nav = []
            if has_next:
                nav.append(Choice("Next page →", value="next"))
            if has_prev:
                nav.append(Choice("← Previous page", value="prev"))
            nav.append(Choice("Done", value="done"))
            pick = _select_quit(f"Page {page+1} ({end}/{len(entries)})", choices=nav)
            if pick == "next":
                page += 1
            elif pick == "prev":
                page -= 1
            else:
                return

    def _view_entry(self):
        if not self._entries:
            console.print("[red]No corpus loaded[/red]")
            return
        idx = _text(f"Entry ID (0-{len(self._entries)-1})", default="0")
        if idx is None:
            return
        try:
            i = int(idx)
            e = self._entries[i]
            header = f"Topics: {e.get('topics', '')}\n\n" if e.get("topics") else ""
            console.print(
                Panel(
                    header + e["text"],
                    title=f"Entry {i}",
                    box=box.ROUNDED,
                    border_style="cyan",
                )
            )
        except (ValueError, IndexError):
            console.print("[red]✗ Invalid ID[/red]")

    def _search_corpus(self):
        if not self._entries:
            console.print("[red]No corpus loaded[/red]")
            return
        term = _text("Search term")
        if term is None:
            return
        results = [e for e in self._entries if term.lower() in e["text"].lower()]
        console.print(f"[green]Found {len(results)} matches[/green]")
        if results:
            self._display_entries(results)

    def _filter_corpus(self):
        if not self._entries:
            console.print("[red]No corpus loaded[/red]")
            return
        topic = _select_quit("Filter topic", choices=_topic_choices())
        if topic is None:
            return
        results = [
            e for e in self._entries if topic.lower() in e.get("topics", "").lower()
        ]
        console.print(f"[green]Found {len(results)} matches[/green]")
        if results:
            self._display_entries(results)

    def _export_corpus(self, fmt):
        if not self._entries:
            console.print("[red]No corpus data to export[/red]")
            return
        base = Path(self._loaded_path) if self._loaded_path else Path("export")
        path = str(base.with_suffix(f".export.{fmt}"))
        if not _confirm(f"Export to {path}?", default=True):
            return
        try:
            if fmt == "csv":
                with open(path, "w", newline="") as f:
                    w = csv.writer(f)
                    w.writerow(["id", "text", "topics", "quality"])
                    for i, e in enumerate(self._entries):
                        w.writerow([i, e["text"], e["topics"], e.get("quality", "")])
            else:
                with open(path, "w") as f:
                    json.dump(self._entries, f, indent=2)
            console.print(f"[green]✓ Exported to {path}[/green]")
            tlog.info("EXPORT  %s → %s", fmt, path)
        except Exception as e:
            console.print(f"[red]✗ Export failed: {e}[/red]")

    def _preprocess_raw(self):
        raw_dir = _path("Raw corpus directory", default=self._raw_dir)
        if raw_dir is None:
            return
        output_path = _path("Output corpus JSON path", default=self._corpus_path)
        if output_path is None:
            return
        if not _confirm(f"Preprocess {raw_dir} → {output_path}?", default=True):
            return
        try:
            from ..services.corpus_preprocessor import build_corpus

            with console.status(
                "[bold green]Preprocessing raw corpus...", spinner="dots"
            ):
                count = build_corpus(
                    raw_dir=Path(raw_dir), output_path=Path(output_path)
                )
            self._raw_dir = raw_dir
            self._corpus_path = output_path
            console.print(
                f"[green]✓ Preprocessed {count} entries → {output_path}[/green]"
            )
            self._load_corpus(output_path)
            tlog.info("PREPROCESS  %d entries → %s", count, output_path)
        except Exception as e:
            console.print(f"[red]✗ Preprocess failed: {e}[/red]")
            console.print(
                "[dim]Tip: ensure raw directory exists with subdirectories[/dim]"
            )

    def _parse_json(self, p):
        with open(p) as f:
            data = json.load(f)
        if isinstance(data, list):
            return self._normalize_entries(data)
        if isinstance(data, dict) and "entries" in data:
            return self._normalize_entries(data["entries"])
        return [{"text": json.dumps(data, indent=2), "topics": "", "quality": "N/A"}]

    def _normalize_entries(self, items):
        return [
            {
                "text": e.get("text", str(e)),
                "topics": (
                    ", ".join(e["topic"])
                    if isinstance(e.get("topic"), list)
                    else ", ".join(e.get("topics", []))
                ),
                "quality": e.get("quality_score", "N/A"),
            }
            for e in items
        ]

    def _parse_csv(self, p):
        entries = []
        with open(p) as f:
            for row in csv.DictReader(f):
                entries.append(
                    {
                        "text": row.get("text", row.get("content", "")),
                        "topics": row.get("topic_labels", row.get("topics", "")),
                        "quality": row.get("quality_score", row.get("quality", "N/A")),
                    }
                )
        return entries

    def _parse_txt(self, p):
        return [{"text": p.read_text(), "topics": "", "quality": "N/A"}]

    def import_cases_flow(self):
        """Import SG case summaries from PDF/DOCX into corpus/cases/ as structured JSON."""
        console.print("\n[bold yellow]Import SG Case Summaries[/bold yellow]")
        console.print(
            "[dim]Import PDF/DOCX files containing SG case summaries.\n"
            "Text will be extracted and stored as structured JSON in corpus/cases/.[/dim]\n"
        )
        file_path = _path("Path to case file (PDF/DOCX)", default="")
        if not file_path:
            return
        p = Path(file_path)
        if not p.exists():
            console.print(f"[red]✗ File not found: {file_path}[/red]")
            return
        if p.suffix.lower() not in (".pdf", ".docx", ".txt"):
            console.print("[red]✗ Unsupported format. Use PDF, DOCX, or TXT.[/red]")
            return
        try:
            from ..services.corpus_preprocessor import extract_text, normalize_text

            with console.status("[bold green]Extracting text...", spinner="dots"):
                raw_text = normalize_text(extract_text(p))
            if not raw_text or len(raw_text) < 50:
                console.print("[red]✗ No usable text extracted from file[/red]")
                return
            console.print(
                Panel(
                    raw_text[:1500] + ("..." if len(raw_text) > 1500 else ""),
                    title=f"Extracted from {p.name}",
                    box=box.ROUNDED,
                    border_style="green",
                )
            )
            case_name = _text("Case name", default=p.stem.replace("_", " ").title())
            if case_name is None:
                return
            citation = _text("Citation (e.g. [2020] SGCA 1)", default="")
            if citation is None:
                return
            summary = _text(
                "Brief summary (or press Enter to use full text)", default=""
            )
            topics = _checkbox("Related topics", choices=_topic_choices())
            if topics is None:
                return
            case_entry = {
                "case_name": case_name,
                "citation": citation,
                "summary": summary if summary else raw_text,
                "full_text": raw_text,
                "topics": topics,
                "source_file": str(p),
            }
            cases_dir = Path("corpus/cases")
            cases_dir.mkdir(parents=True, exist_ok=True)
            safe_name = re.sub(r"[^\w\-]", "_", case_name.lower())[:60]
            out_path = cases_dir / f"{safe_name}.json"
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(case_entry, f, indent=2, ensure_ascii=False)
            console.print(f"[green]✓ Case saved → {out_path}[/green]")
            tlog.info("IMPORT_CASE  %s → %s", case_name, out_path)
        except Exception as e:
            console.print(f"[red]✗ Import failed: {e}[/red]")
            tlog.info("ERROR  import_cases: %s", e)
