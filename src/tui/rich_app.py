#!/usr/bin/env python3
"""
Jikai TUI Application
"""

import sys
import os
from pathlib import Path

from rich.panel import Panel
from rich import box
from rich.layout import Layout
from questionary import Choice

from src.tui.console import console, setup_logging, tlog
from src.tui.inputs import _select_quit
from src.tui.constants import TITLE, VERSION, LOG_LEVEL

from src.tui.flows.ocr import OCRFlowMixin
from src.tui.flows.corpus import CorpusFlowMixin
from src.tui.flows.label import LabelFlowMixin
from src.tui.flows.train import TrainFlowMixin
from src.tui.flows.gen import GenerationFlowMixin
from src.tui.flows.history import HistoryFlowMixin
from src.tui.flows.settings import SettingsFlowMixin
from src.tui.flows.cleanup import CleanupMixin


class JikaiTUI(
    OCRFlowMixin,
    CorpusFlowMixin,
    LabelFlowMixin,
    TrainFlowMixin,
    GenerationFlowMixin,
    HistoryFlowMixin,
    SettingsFlowMixin,
    CleanupMixin,
):
    """
    Main TUI class for Jikai.
    Combines all feature mixins into a single application context.
    """

    def __init__(self):
        # State
        self._loaded_path = ""
        self._entries: list = []
        
        # Paths (defaults, can be overridden by env in settings flow)
        self._corpus_path = os.getenv("CORPUS_PATH", "corpus/clean/tort/corpus.json")
        self._raw_dir = "corpus/raw"
        self._models_dir = "models"
        self._train_data = "corpus/data/train.csv"
        
        # Navigation stack for breadcrumbs
        self._nav_path = ["Main"]

    def run(self):
        """Application entry point."""
        setup_logging(LOG_LEVEL)
        self.display_banner()
        
        # Initialize services and environment
        self._start_services()
        
        # First-run wizard if needed
        if self._needs_first_run():
            self.first_run_wizard()
        
        # Main Loop
        self.main_menu()

    def display_banner(self):
        console.clear()
        console.print(
            Panel(
                f"[bold cyan]{TITLE}[/bold cyan]  [dim]v{VERSION}[/dim]\n"
                "[italic]Singapore Legal Hypothetical Generator[/italic]",
                box=box.DOUBLE,
                border_style="cyan",
            )
        )

    def main_menu(self):
        self._nav_path = ["Main"]
        
        # Quick check for env updates to paths
        self._corpus_path = os.getenv("CORPUS_PATH", self._corpus_path)

        while True:
            self._render_breadcrumb()
            self._render_status_bar()
            
            console.print("\n[bold yellow]Main Menu[/bold yellow]")
            
            # Determine available actions based on state
            corpus_ok = self._corpus_ready()
            
            choices = []
            
            # 1. Corpus Management
            choices.append(Choice("Browse Corpus", value="corpus"))
            
            # 2. Generation (Core Feature)
            # Always allow, but warn if no corpus/models?
            # Actually generation relies on LLM mostly, RAG is optional.
            choices.append(Choice("Generate Hypothetical", value="generate"))
            
            # 3. Import/Label/Train (Workflows)
            choices.append(Choice("Tools & Workflows...", value="tools"))
            
            # 4. History
            choices.append(Choice("History & Exports", value="history"))
            
            # 5. More (Settings, Cleanup, etc)
            choices.append(Choice("More...", value="more"))

            choice = _select_quit(
                "What would you like to do?",
                choices=choices,
            )
            
            if choice is None:
                # Exit
                console.print("\n[dim]Goodbye![/dim]")
                sys.exit(0)

            if choice == "corpus":
                self._push_nav("Corpus")
                self.corpus_flow()
                self._pop_nav()
            elif choice == "generate":
                self._push_nav("Generate")
                self.generate_flow()
                self._pop_nav()
            elif choice == "tools":
                self._push_nav("Tools")
                self._tools_menu()
                self._pop_nav()
            elif choice == "history":
                self._push_nav("History")
                self.history_flow()
                self._pop_nav()
            elif choice == "more":
                self._push_nav("More")
                self._more_menu()
                self._pop_nav()

    def _tools_menu(self):
        """Sub-menu for tools (Import, Label, Train)."""
        while True:
            self._render_breadcrumb()
            console.print("\n[bold yellow]Tools & Workflows[/bold yellow]")
            
            choices = [
                Choice("Import Case Summaries (PDF/DOCX → JSON)", value="import_cases"),
                Choice("OCR / Preprocess Raw Documents", value="ocr"),
                Choice("Label Corpus for Training", value="label"),
                Choice("Train/Retrain ML Models", value="train"),
                Choice("Generate Embeddings (ChromaDB)", value="embed"),
                Choice("Batch Generate (Evaluation)", value="batch"),
            ]
            
            c = _select_quit("Select tool", choices=choices)
            if c is None:
                return

            if c == "import_cases":
                self.import_cases_flow()
            elif c == "ocr":
                self.ocr_flow()
            elif c == "label":
                self.label_flow()
            elif c == "train":
                self.train_flow()
            elif c == "embed":
                self.embed_flow()
            elif c == "batch":
                self.batch_generate_flow()

    def _more_menu(self):
        """Sub-menu for extra settings and cleanup."""
        while True:
            self._render_breadcrumb()
            console.print("\n[bold yellow]More Options[/bold yellow]")
            
            choices = [
                Choice("Settings (API Keys, Paths, Defaults)", value="settings"),
                Choice("Manage Providers (Ollama, OpenAI...)", value="providers"),
                Choice("System Cleanup / Reset", value="cleanup"),
                Choice("Help / About", value="help"),
            ]
            
            c = _select_quit("Select option", choices=choices)
            if c is None:
                return

            if c == "settings":
                self.settings_flow()
            elif c == "providers":
                self.providers_flow()
            elif c == "cleanup":
                self.cleanup_flow()
            elif c == "help":
                console.print(Panel(
                    "[bold]Jikai Help[/bold]\n\n"
                    "Jikai is a tool for generating Singapore tort law hypotheticals.\n"
                    "- [cyan]Browse Corpus[/cyan]: View/search the legal knowledge base.\n"
                    "- [cyan]Generate[/cyan]: Create new hypotheticals using LLMs.\n"
                    "- [cyan]Tools[/cyan]: Import data, label entries, and train quality models.\n",
                    title="About",
                    box=box.ROUNDED
                ))
                _select_quit("Press Enter to return", choices=[Choice("Back", value="back")])

    def _render_breadcrumb(self):
        """Show current navigation path."""
        console.print(f"\n[dim]{' > '.join(self._nav_path)}[/dim]")

    def _render_status_bar(self):
        """Show system status (corpus, models, services)."""
        status = []
        
        # Corpus Status
        if self._corpus_ready():
            status.append("[green]Corpus: OK[/green]")
        else:
            status.append("[red]Corpus: Missing[/red]")
            
        # Model Status
        if self._models_ready():
            status.append("[green]Models: Active[/green]")
        else:
            status.append("[dim]Models: None[/dim]")
            
        # Embeddings Status
        if self._embeddings_ready():
            status.append("[green]Vector DB: Ready[/green]")
        else:
            status.append("[dim]Vector DB: Not indexed[/dim]")

        console.print(Panel(
            "  |  ".join(status),
            box=box.SIMPLE,
            style="dim"
        ))

    def _push_nav(self, name):
        self._nav_path.append(name)

    def _pop_nav(self):
        if len(self._nav_path) > 1:
            self._nav_path.pop()

    def _corpus_ready(self):
        return Path(self._corpus_path).exists() and Path(self._corpus_path).stat().st_size > 100

    def _labelled_ready(self):
        return Path(self._train_data).exists()

    def _models_ready(self):
        # Check for any .joblib model
        return any(Path(self._models_dir).glob("*.joblib"))

    def _embeddings_ready(self):
        # Check for chroma db dir
        db_path = os.getenv("DATABASE_PATH", "chroma_db")
        return Path(db_path).exists() and any(Path(db_path).iterdir())


if __name__ == "__main__":
    try:
        app = JikaiTUI()
        app.run()
    except KeyboardInterrupt:
        console.print("\n[dim]Interrupted. Exiting...[/dim]")
        sys.exit(0)
    except Exception as e:
        console.print(f"\n[red][FATAL] {e}[/red]")
        tlog.critical("FATAL: %s", e, exc_info=True)
        sys.exit(1)
