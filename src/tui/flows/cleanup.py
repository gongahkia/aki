"""Cleanup flow."""

import shutil
from pathlib import Path

from rich import box
from rich.table import Table
from questionary import Choice

from src.tui.console import console, tlog
from src.tui.inputs import _select_quit, _confirm, _checkbox
from src.tui.constants import HISTORY_PATH


class CleanupMixin:
    """Mixin for cleanup flows."""

    def cleanup_flow(self):
        console.print("\n[bold yellow]Cleanup & Reset[/bold yellow]")
        options = [
            ("exports", "Delete all exported files (docx/pdf/csv)"),
            ("chroma", "Delete ChromaDB vector database"),
            ("models", "Delete trained ML models"),
            ("logs", "Delete application logs"),
            ("cache", "Delete Python __pycache__"),
            ("history", "Delete generation history"),
            ("env", "Delete .env configuration"),
        ]
        
        # Calculate sizes
        sizes = {}
        for key, _ in options:
            sizes[key] = 0
            if key == "exports":
                p = Path("exports")
                if p.exists():
                    sizes[key] = sum(f.stat().st_size for f in p.glob("**/*") if f.is_file())
            elif key == "chroma":
                # Assuming DATABASE_PATH from env or default
                # Just use default reasonable path or check env
                p = Path("chroma_db") # This might be dynamic
                if p.exists():
                     sizes[key] = sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
            elif key == "models":
                p = Path("models")
                if p.exists():
                    sizes[key] = sum(f.stat().st_size for f in p.glob("*.joblib"))
            elif key == "logs":
                p = Path("logs")
                if p.exists():
                     sizes[key] = sum(f.stat().st_size for f in p.glob("*.log"))
            elif key == "history":
                if Path(HISTORY_PATH).exists():
                    sizes[key] = Path(HISTORY_PATH).stat().st_size
            elif key == "env":
                if Path(".env").exists():
                    sizes[key] = Path(".env").stat().st_size
            elif key == "cache":
                # Count all __pycache__
                total = 0
                for p in Path(".").rglob("__pycache__"):
                    total += sum(f.stat().st_size for f in p.glob("*"))
                sizes[key] = total

        choices_list = []
        for key, desc in options:
            size_str = f"({sizes[key] / 1024:.1f} KB)"
            if sizes[key] > 1024 * 1024:
                size_str = f"({sizes[key] / (1024*1024):.1f} MB)"
            choices_list.append(Choice(f"{desc} {size_str}", value=key))

        selected = _checkbox("Select items to delete", choices=choices_list)
        if not selected:
            return

        if not _confirm(f"DELETE {len(selected)} items? This is permanent.", default=False):
            return

        for item in selected:
            try:
                if item == "exports":
                    shutil.rmtree("exports", ignore_errors=True)
                    console.print("[green]✓ Deleted exports/[/green]")
                elif item == "chroma":
                    shutil.rmtree("chroma_db", ignore_errors=True)
                    console.print("[green]✓ Deleted chroma_db/[/green]")
                elif item == "models":
                    for f in Path("models").glob("*.joblib"):
                        f.unlink()
                    console.print("[green]✓ Deleted trained models[/green]")
                elif item == "logs":
                    shutil.rmtree("logs", ignore_errors=True)
                    console.print("[green]✓ Deleted logs/[/green]")
                elif item == "history":
                    Path(HISTORY_PATH).unlink(missing_ok=True)
                    console.print("[green]✓ Deleted history[/green]")
                elif item == "env":
                    Path(".env").unlink(missing_ok=True)
                    console.print("[green]✓ Deleted .env[/green]")
                elif item == "cache":
                     for p in Path(".").rglob("__pycache__"):
                        shutil.rmtree(p, ignore_errors=True)
                     console.print("[green]✓ Deleted __pycache__[/green]")
            except Exception as e:
                console.print(f"[red]✗ Failed to delete {item}: {e}[/red]")
