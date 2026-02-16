"""Jikai Rich TUI - Procedural terminal interface (caipng-style)."""
import asyncio
import csv
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List
from rich import box
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import (BarColumn, Progress, SpinnerColumn, TextColumn,
                           TimeElapsedColumn)
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.text import Text

console = Console()
LOG_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'logs')
os.makedirs(LOG_DIR, exist_ok=True)
LOG_PATH = os.path.join(LOG_DIR, 'tui.log')
_fh = logging.FileHandler(LOG_PATH, mode='w', encoding='utf-8')
_fh.setFormatter(logging.Formatter('%(asctime)s  %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
tlog = logging.getLogger('jikai.tui')
tlog.setLevel(logging.INFO)
tlog.addHandler(_fh)

TOPICS = [
    "negligence", "duty_of_care", "causation", "remoteness",
    "battery", "assault", "false_imprisonment", "defamation",
    "private_nuisance", "trespass_to_land", "vicarious_liability",
    "strict_liability", "harassment", "occupiers_liability",
    "product_liability", "contributory_negligence", "economic_loss",
    "psychiatric_harm", "employers_liability",
]
PROVIDERS = ["ollama", "openai", "anthropic", "google", "local"]

def _run_async(coro):
    """Run async coroutine from synchronous context."""
    return asyncio.run(coro)

class JikaiTUI:
    def __init__(self):
        self._loaded_path = ""
        self._entries: list = []

    def display_banner(self):
        tlog.info('=== TUI session started ===')
        console.print(Panel(
            "[bold cyan]Jikai - Legal Hypothetical Generator[/bold cyan]\n"
            "[dim]AI-powered Singapore tort law hypothetical generation[/dim]",
            box=box.DOUBLE, border_style="cyan"))

    def main_menu(self):
        while True:
            console.print("\n[bold yellow]Main Menu[/bold yellow]")
            console.print("=" * 60)
            menu = Table(box=box.SIMPLE, show_header=False)
            menu.add_column("Key", style="cyan", width=4)
            menu.add_column("Action", style="yellow")
            menu.add_row("1", "Generate Hypothetical")
            menu.add_row("2", "Train ML Models")
            menu.add_row("3", "Browse Corpus")
            menu.add_row("4", "Settings")
            menu.add_row("5", "Providers")
            menu.add_row("6", "Quit")
            console.print(menu)
            choice = Prompt.ask("[bold]Select[/bold]",
                               choices=["1", "2", "3", "4", "5", "6"], default="1")
            if choice == "1": self.generate_flow()
            elif choice == "2": self.train_flow()
            elif choice == "3": self.corpus_flow()
            elif choice == "4": self.settings_flow()
            elif choice == "5": self.providers_flow()
            elif choice == "6":
                console.print("[dim]Goodbye.[/dim]")
                tlog.info('=== TUI session ended ===')
                break

    # ── generate ────────────────────────────────────────────────
    def generate_flow(self):
        while True:
            console.print("\n[bold yellow]Generate Hypothetical[/bold yellow]")
            console.print("=" * 60)
            tt = Table(title="Available Topics", box=box.SIMPLE)
            tt.add_column("#", style="cyan", width=4)
            tt.add_column("Topic", style="yellow")
            for i, t in enumerate(TOPICS, 1):
                tt.add_row(str(i), t)
            console.print(tt)
            topic_idx = Prompt.ask("Topic number", default="1")
            try: topic = TOPICS[int(topic_idx) - 1]
            except (ValueError, IndexError): topic = "negligence"
            provider = Prompt.ask("Provider", choices=PROVIDERS, default="ollama")
            model_name = Prompt.ask("Model [dim](enter to skip)[/dim]", default="")
            complexity = Prompt.ask("Complexity (1-5)", default="3")
            parties = Prompt.ask("Parties (2-5)", default="3")
            method = Prompt.ask("Method",
                                choices=["pure_llm", "ml_assisted", "hybrid"],
                                default="pure_llm")
            cfg = Table(box=box.SIMPLE, title="Generation Config")
            cfg.add_column("Parameter", style="cyan")
            cfg.add_column("Value", style="yellow")
            cfg.add_row("Topic", topic)
            cfg.add_row("Provider", provider)
            cfg.add_row("Model", model_name or "(default)")
            cfg.add_row("Complexity", complexity)
            cfg.add_row("Parties", parties)
            cfg.add_row("Method", method)
            console.print(cfg)
            if not Confirm.ask("Proceed with generation?", default=True):
                return
            tlog.info('GENERATE  topic=%s provider=%s model=%s complexity=%s parties=%s method=%s',
                       topic, provider, model_name, complexity, parties, method)
            self._do_generate(topic, provider, model_name or None,
                              int(complexity), int(parties), method)
            if not Confirm.ask("\nGenerate another?", default=False):
                return

    def _do_generate(self, topic, provider, model, complexity, parties, method):
        try:
            from ..services.llm_service import LLMRequest, llm_service
            request = LLMRequest(
                prompt=(f"Generate a Singapore tort law hypothetical about {topic}"
                        f" with {parties} parties at complexity {complexity}/5."),
                stream=True)
            async def _stream():
                chunks: List[str] = []
                with Live(Text("Generating..."), console=console, refresh_per_second=4) as live:
                    async for chunk in llm_service.stream_generate(
                            request, provider=provider, model=model):
                        chunks.append(chunk)
                        live.update(Text("".join(chunks)))
                return "".join(chunks)
            try:
                result = _run_async(_stream())
                if result:
                    console.print(Panel(result, title="Generated Hypothetical",
                                        box=box.ROUNDED, border_style="green"))
                    tlog.info('GENERATE  stream success, len=%d', len(result))
                    return
            except Exception as stream_err:
                tlog.info('GENERATE  stream failed: %s, trying full', stream_err)
                console.print(f"[yellow]Stream unavailable ({stream_err}), using full generation...[/yellow]")
            from ..services.hypothetical_service import GenerationRequest, hypothetical_service
            async def _full():
                req = GenerationRequest(
                    topics=[topic],
                    number_parties=max(2, min(5, parties)),
                    complexity_level=str(complexity),
                    method=method, provider=provider, model=model)
                return await hypothetical_service.generate_hypothetical(req)
            with console.status("[bold green]Generating hypothetical...", spinner="dots"):
                response = _run_async(_full())
            console.print(Panel(response.hypothetical, title="Generated Hypothetical",
                                box=box.ROUNDED, border_style="green"))
            if response.analysis:
                console.print(Panel(response.analysis, title="Legal Analysis",
                                    box=box.ROUNDED, border_style="cyan"))
            vr = response.validation_results
            if vr:
                vt = Table(title="Validation Results", box=box.ROUNDED)
                vt.add_column("Check", style="cyan")
                vt.add_column("Result", style="yellow")
                vt.add_row("Quality Score", str(vr.get("quality_score", "N/A")))
                vt.add_row("Passed", "[green]Yes[/green]" if vr.get("passed") else "[red]No[/red]")
                console.print(vt)
            tlog.info('GENERATE  full success')
        except Exception as e:
            console.print(f"[red]✗ Generation failed: {e}[/red]")
            console.print("[dim]Tip: check provider health via Providers menu[/dim]")
            tlog.info('ERROR  generation: %s', e)

    # ── train ───────────────────────────────────────────────────
    def train_flow(self):
        console.print("\n[bold yellow]Train ML Models[/bold yellow]")
        console.print("=" * 60)
        data_path = Prompt.ask("Training data path", default="corpus/labelled/sample.csv")
        train_cls = Confirm.ask("Train classifier?", default=True)
        train_reg = Confirm.ask("Train regressor?", default=True)
        train_clu = Confirm.ask("Train clusterer?", default=True)
        n_clusters = Prompt.ask("Number of clusters", default="5")
        test_split = Prompt.ask("Test split", default="0.2")
        max_features = Prompt.ask("Max features", default="5000")
        cfg = Table(box=box.SIMPLE, title="Training Config")
        cfg.add_column("Parameter", style="cyan")
        cfg.add_column("Value", style="yellow")
        cfg.add_row("Data Path", data_path)
        cfg.add_row("Classifier", "Yes" if train_cls else "No")
        cfg.add_row("Regressor", "Yes" if train_reg else "No")
        cfg.add_row("Clusterer", "Yes" if train_clu else "No")
        cfg.add_row("Clusters", n_clusters)
        cfg.add_row("Test Split", test_split)
        cfg.add_row("Max Features", max_features)
        console.print(cfg)
        if not Confirm.ask("Proceed with training?", default=True):
            return
        tlog.info('TRAIN  data=%s cls=%s reg=%s clu=%s', data_path, train_cls, train_reg, train_clu)
        self._do_train(data_path, int(n_clusters), int(max_features))

    def _do_train(self, data_path, n_clusters, max_features):
        try:
            from ..ml.pipeline import MLPipeline
            pipeline = MLPipeline()
            with Progress(
                SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                BarColumn(), TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeElapsedColumn(), console=console,
            ) as progress:
                task = progress.add_task("[cyan]Training ML pipeline", total=100)
                def on_progress(pct, msg):
                    progress.update(task, completed=int(pct * 100),
                                    description=f"[cyan]{msg}")
                metrics = pipeline.train_all(data_path, progress_callback=on_progress,
                                             n_clusters=n_clusters, max_features=max_features)
            console.print("\n[bold green]✓ Training Complete![/bold green]")
            mt = Table(title="Training Metrics", box=box.ROUNDED)
            mt.add_column("Model", style="cyan")
            mt.add_column("Metrics", style="yellow")
            for name, vals in metrics.items():
                mt.add_row(name, str(vals))
            console.print(mt)
            tlog.info('TRAIN  complete')
        except Exception as e:
            console.print(f"[red]✗ Training failed: {e}[/red]")
            console.print("[dim]Tip: ensure training CSV exists at specified path[/dim]")
            tlog.info('ERROR  training: %s', e)

    # ── corpus ──────────────────────────────────────────────────
    def corpus_flow(self):
        console.print("\n[bold yellow]Browse Corpus[/bold yellow]")
        console.print("=" * 60)
        path = Prompt.ask("Corpus file path", default="corpus/clean/tort/corpus.json")
        self._load_corpus(path)
        while True:
            console.print("\n[bold yellow]Corpus Menu[/bold yellow]")
            menu = Table(box=box.SIMPLE, show_header=False)
            menu.add_column("Key", style="cyan", width=4)
            menu.add_column("Action", style="yellow")
            menu.add_row("1", "View entry")
            menu.add_row("2", "Search")
            menu.add_row("3", "Filter by topic")
            menu.add_row("4", "Export CSV")
            menu.add_row("5", "Export JSON")
            menu.add_row("6", "Preprocess raw")
            menu.add_row("7", "Load different file")
            menu.add_row("8", "Back")
            console.print(menu)
            c = Prompt.ask("Select", choices=["1","2","3","4","5","6","7","8"], default="8")
            if c == "1": self._view_entry()
            elif c == "2": self._search_corpus()
            elif c == "3": self._filter_corpus()
            elif c == "4": self._export_corpus("csv")
            elif c == "5": self._export_corpus("json")
            elif c == "6": self._preprocess_raw()
            elif c == "7":
                path = Prompt.ask("Corpus file path",
                                  default=self._loaded_path or "corpus/clean/tort/corpus.json")
                self._load_corpus(path)
            elif c == "8": return

    def _load_corpus(self, path):
        try:
            p = Path(path)
            if not p.exists():
                console.print(f"[red]✗ File not found: {path}[/red]")
                return
            ext = p.suffix.lower()
            if ext == ".json": self._entries = self._parse_json(p)
            elif ext == ".csv": self._entries = self._parse_csv(p)
            elif ext == ".txt": self._entries = self._parse_txt(p)
            else:
                console.print(f"[red]✗ Unsupported type: {ext}[/red]")
                return
            self._loaded_path = path
            console.print(f"[green]✓ Loaded {len(self._entries)} entries from {p.name}[/green]")
            self._display_entries(self._entries)
            tlog.info('CORPUS  loaded %d entries from %s', len(self._entries), path)
        except Exception as e:
            console.print(f"[red]✗ Load error: {e}[/red]")

    def _display_entries(self, entries, page=0, page_size=20):
        start = page * page_size
        end = min(start + page_size, len(entries))
        if start >= len(entries):
            return
        table = Table(title=f"Entries [{start+1}-{end} of {len(entries)}]", box=box.ROUNDED)
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
            table.add_row(str(i), e.get("topics", ""), str(e.get("quality", "N/A")),
                          str(len(text.split())), preview)
        console.print(table)
        if end < len(entries):
            if Confirm.ask(f"Next page? ({end}/{len(entries)})", default=True):
                self._display_entries(entries, page + 1, page_size)

    def _view_entry(self):
        if not self._entries:
            console.print("[red]No corpus loaded[/red]")
            return
        idx = Prompt.ask(f"Entry ID (0-{len(self._entries)-1})", default="0")
        try:
            i = int(idx)
            e = self._entries[i]
            header = f"Topics: {e.get('topics','')}\n\n" if e.get("topics") else ""
            console.print(Panel(header + e["text"], title=f"Entry {i}",
                                box=box.ROUNDED, border_style="cyan"))
        except (ValueError, IndexError):
            console.print("[red]✗ Invalid ID[/red]")

    def _search_corpus(self):
        if not self._entries:
            console.print("[red]No corpus loaded[/red]")
            return
        term = Prompt.ask("Search term")
        results = [e for e in self._entries if term.lower() in e["text"].lower()]
        console.print(f"[green]Found {len(results)} matches[/green]")
        if results:
            self._display_entries(results)

    def _filter_corpus(self):
        if not self._entries:
            console.print("[red]No corpus loaded[/red]")
            return
        topic = Prompt.ask("Filter topic")
        results = [e for e in self._entries if topic.lower() in e.get("topics", "").lower()]
        console.print(f"[green]Found {len(results)} matches[/green]")
        if results:
            self._display_entries(results)

    def _export_corpus(self, fmt):
        if not self._entries:
            console.print("[red]No corpus data to export[/red]")
            return
        base = Path(self._loaded_path) if self._loaded_path else Path("export")
        path = str(base.with_suffix(f".export.{fmt}"))
        if not Confirm.ask(f"Export to {path}?", default=True):
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
            tlog.info('EXPORT  %s → %s', fmt, path)
        except Exception as e:
            console.print(f"[red]✗ Export failed: {e}[/red]")

    def _preprocess_raw(self):
        if not Confirm.ask("Preprocess raw corpus files?", default=True):
            return
        try:
            from ..services.corpus_preprocessor import CORPUS_FILE, build_corpus
            with console.status("[bold green]Preprocessing raw corpus...", spinner="dots"):
                count = build_corpus()
            console.print(f"[green]✓ Preprocessed {count} entries → {CORPUS_FILE}[/green]")
            self._load_corpus(str(CORPUS_FILE))
            tlog.info('PREPROCESS  %d entries', count)
        except Exception as e:
            console.print(f"[red]✗ Preprocess failed: {e}[/red]")
            console.print("[dim]Tip: ensure corpus/raw/ directory exists[/dim]")

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
            {"text": e.get("text", str(e)),
             "topics": (", ".join(e["topic"]) if isinstance(e.get("topic"), list)
                        else ", ".join(e.get("topics", []))),
             "quality": e.get("quality_score", "N/A")}
            for e in items]

    def _parse_csv(self, p):
        entries = []
        with open(p) as f:
            for row in csv.DictReader(f):
                entries.append({
                    "text": row.get("text", row.get("content", "")),
                    "topics": row.get("topic_labels", row.get("topics", "")),
                    "quality": row.get("quality_score", row.get("quality", "N/A"))})
        return entries

    def _parse_txt(self, p):
        return [{"text": p.read_text(), "topics": "", "quality": "N/A"}]

    # ── settings ────────────────────────────────────────────────
    def settings_flow(self):
        console.print("\n[bold yellow]Settings[/bold yellow]")
        console.print("=" * 60)
        env = self._load_env()
        def _mask(v):
            if not v: return ""
            return v[:4] + "****" + v[-4:] if len(v) > 8 else "****"
        anthropic_key = Prompt.ask(
            f"Anthropic API Key [dim]({_mask(env.get('ANTHROPIC_API_KEY',''))})[/dim]",
            default=env.get("ANTHROPIC_API_KEY", ""))
        openai_key = Prompt.ask(
            f"OpenAI API Key [dim]({_mask(env.get('OPENAI_API_KEY',''))})[/dim]",
            default=env.get("OPENAI_API_KEY", ""))
        google_key = Prompt.ask(
            f"Google API Key [dim]({_mask(env.get('GOOGLE_API_KEY',''))})[/dim]",
            default=env.get("GOOGLE_API_KEY", ""))
        ollama_host = Prompt.ask("Ollama Host",
            default=env.get("OLLAMA_HOST", "http://localhost:11434"))
        local_host = Prompt.ask("Local LLM Host",
            default=env.get("LOCAL_LLM_HOST", "http://localhost:8080"))
        temperature = Prompt.ask("Default Temperature",
            default=env.get("DEFAULT_TEMPERATURE", "0.7"))
        max_tokens = Prompt.ask("Default Max Tokens",
            default=env.get("DEFAULT_MAX_TOKENS", "2048"))
        corpus_path = Prompt.ask("Corpus Path",
            default=env.get("CORPUS_PATH", "corpus/clean/tort/corpus.json"))
        db_path = Prompt.ask("Database Path",
            default=env.get("DATABASE_PATH", "data/jikai.db"))
        log_level = Prompt.ask("Log Level",
            choices=["DEBUG", "INFO", "WARNING", "ERROR"],
            default=env.get("LOG_LEVEL", "INFO"))
        st = Table(box=box.SIMPLE, title="Settings Summary")
        st.add_column("Setting", style="cyan")
        st.add_column("Value", style="yellow")
        st.add_row("Anthropic Key", _mask(anthropic_key))
        st.add_row("OpenAI Key", _mask(openai_key))
        st.add_row("Google Key", _mask(google_key))
        st.add_row("Ollama Host", ollama_host)
        st.add_row("Local LLM Host", local_host)
        st.add_row("Temperature", temperature)
        st.add_row("Max Tokens", max_tokens)
        st.add_row("Corpus Path", corpus_path)
        st.add_row("Database Path", db_path)
        st.add_row("Log Level", log_level)
        console.print(st)
        if not Confirm.ask("Save settings to .env?", default=True):
            return
        lines = [
            f"ANTHROPIC_API_KEY={anthropic_key}", f"OPENAI_API_KEY={openai_key}",
            f"GOOGLE_API_KEY={google_key}", f"OLLAMA_HOST={ollama_host}",
            f"LOCAL_LLM_HOST={local_host}", f"DEFAULT_TEMPERATURE={temperature}",
            f"DEFAULT_MAX_TOKENS={max_tokens}", f"CORPUS_PATH={corpus_path}",
            f"DATABASE_PATH={db_path}", f"LOG_LEVEL={log_level}",
        ]
        with open(".env", "w") as f:
            f.write("\n".join(lines) + "\n")
        console.print("[green]✓ Settings saved to .env[/green]")
        tlog.info('SETTINGS  saved')

    def _load_env(self):
        vals: Dict[str, str] = {}
        try:
            with open(".env") as f:
                for line in f:
                    line = line.strip()
                    if "=" in line and not line.startswith("#"):
                        k, v = line.split("=", 1)
                        vals[k.strip()] = v.strip()
        except FileNotFoundError:
            pass
        return vals

    # ── providers ───────────────────────────────────────────────
    def providers_flow(self):
        console.print("\n[bold yellow]LLM Providers[/bold yellow]")
        console.print("=" * 60)
        while True:
            menu = Table(box=box.SIMPLE, show_header=False)
            menu.add_column("Key", style="cyan", width=4)
            menu.add_column("Action", style="yellow")
            menu.add_row("1", "Check Health")
            menu.add_row("2", "Set Default Provider")
            menu.add_row("3", "Back")
            console.print(menu)
            c = Prompt.ask("Select", choices=["1", "2", "3"], default="3")
            if c == "1": self._check_health()
            elif c == "2": self._set_default_provider()
            elif c == "3": return

    def _check_health(self):
        try:
            from ..services.llm_service import llm_service
            async def _health():
                h = await llm_service.health_check()
                m = await llm_service.list_models()
                return h, m
            with console.status("[bold green]Checking provider health...", spinner="dots"):
                health, models = _run_async(_health())
            ht = Table(title="Provider Health", box=box.ROUNDED)
            ht.add_column("Provider", style="cyan")
            ht.add_column("Status", style="yellow")
            ht.add_column("Models", style="dim")
            for name, status in health.items():
                healthy = status.get("healthy", False) if isinstance(status, dict) else status
                icon = "[green]✓[/green]" if healthy else "[red]✗[/red]"
                ml = models.get(name, [])
                ht.add_row(name, icon, ", ".join(ml[:5]) if ml else "-")
            console.print(ht)
            tlog.info('HEALTH  %s', {k: str(v) for k, v in health.items()})
        except Exception as e:
            console.print(f"[red]✗ Health check failed: {e}[/red]")

    def _set_default_provider(self):
        provider = Prompt.ask("Default provider", choices=PROVIDERS, default="ollama")
        try:
            from ..services.llm_service import llm_service
            llm_service.select_provider(provider)
            console.print(f"[green]✓ Default provider: {provider}[/green]")
            tlog.info('PROVIDER  default=%s', provider)
        except Exception as e:
            console.print(f"[red]✗ Failed: {e}[/red]")

    # ── entry point ─────────────────────────────────────────────
    def run(self):
        self.display_banner()
        self.main_menu()

if __name__ == '__main__':
    JikaiTUI().run()
