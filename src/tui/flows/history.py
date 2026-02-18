"""History management flow."""

import json
from datetime import datetime
from pathlib import Path

from rich import box
from rich.panel import Panel
from rich.table import Table
from questionary import Choice

from src.tui.console import console, tlog
from src.tui.inputs import _select_quit, _confirm
from src.tui.constants import HISTORY_PATH


class HistoryFlowMixin:
    """Mixin for history management flows."""

    def history_flow(self):
        console.print("\n[bold yellow]History & Exports[/bold yellow]")
        history = self._load_history()
        if not history:
            console.print("[dim]No generation history found.[/dim]")
            return
        
        # Paginated view of history
        self._display_history(history)
        
        while True:
            c = _select_quit(
                "History Action",
                choices=[
                    Choice("View detailed record", value="view"),
                    Choice("Export record to DOCX", value="export"),
                    Choice("Delete record", value="delete"),
                    Choice("Clear all history", value="clear"),
                ],
            )
            if c is None:
                return

            if c == "view":
                idx = _select_quit(
                    "Select record",
                    choices=[
                        Choice(
                            f"{i+1}. {r.get('timestamp','')} - {r.get('config',{}).get('topic','?')}",
                            value=str(i),
                        )
                        for i, r in enumerate(history[-20:])  # Show last 20
                    ],
                )
                if idx is None:
                    continue
                record = history[int(idx)]
                console.print(
                    Panel(
                        record.get("hypothetical", ""),
                        title=f"{record.get('timestamp')} ({record.get('validation_score','N/A')}/10)",
                        subtitle=str(record.get("config", "")),
                        box=box.ROUNDED,
                    )
                )
                if record.get("analysis"):
                    console.print(
                        Panel(
                            record.get("analysis", ""),
                            title="Analysis",
                            box=box.ROUNDED,
                            border_style="dim",
                        )
                    )

            elif c == "export":
                # Delegate to export flow but pre-fill history selection?
                # Actually export_flow handles history selection.
                # Just call it directly if self.export_flow is available (from GenerationFlowMixin)
                if hasattr(self, "export_flow"):
                    self.export_flow()
                else:
                    console.print("[red]Export flow not available[/red]")

            elif c == "delete":
                idx = _select_quit(
                    "Delete record",
                    choices=[
                        Choice(
                            f"{i+1}. {r.get('timestamp','')} - {r.get('config',{}).get('topic','?')}",
                            value=str(i),
                        )
                        for i, r in enumerate(history[-20:])
                    ],
                )
                if idx is None:
                    continue
                if _confirm("Are you sure?"):
                    del history[int(idx)]
                    with open(HISTORY_PATH, "w") as f:
                        json.dump(history, f, indent=2)
                    console.print("[green]Deleted.[/green]")
                    history = self._load_history()  # Reload

            elif c == "clear":
                if _confirm("Clear ALL history? This cannot be undone."):
                    with open(HISTORY_PATH, "w") as f:
                        json.dump([], f)
                    console.print("[green]History cleared.[/green]")
                    return

    def _display_history(self, history, limit=10):
        table = Table(title=f"Recent History (Last {limit})", box=box.SIMPLE)
        table.add_column("#", style="cyan", width=3)
        table.add_column("Time", style="dim", width=16)
        table.add_column("Topic", style="yellow")
        table.add_column("Qual", style="green", width=5)
        table.add_column("Preview", style="white")

        # Show most recent first
        subset = history[-limit:]
        subset.reverse()
        
        for i, r in enumerate(subset):
            idx = len(history) - i 
            ts = r.get("timestamp", "")[:16]  # Truncate seconds
            cfg = r.get("config", {})
            topic = cfg.get("topic", "?")
            score = r.get("validation_score", "N/A")
            if isinstance(score, float):
                score = f"{score:.1f}"
            text = r.get("hypothetical", "")
            preview = (text[:50] + "...") if len(text) > 50 else text
            preview = preview.replace("\n", " ")
            table.add_row(str(idx), ts, topic, str(score), preview)
        
        console.print(table)

    def _load_history(self):
        if not Path(HISTORY_PATH).exists():
            return []
        try:
            with open(HISTORY_PATH) as f:
                return json.load(f)
        except Exception:
            return []

    def _save_to_history(self, record):
        history = self._load_history()
        record["timestamp"] = datetime.now().isoformat()
        history.append(record)
        try:
            Path(HISTORY_PATH).parent.mkdir(parents=True, exist_ok=True)
            with open(HISTORY_PATH, "w") as f:
                json.dump(history, f, indent=2)
            tlog.info("HISTORY  saved record")
        except Exception as e:
            tlog.error("HISTORY  save failed: %s", e)
