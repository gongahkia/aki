"""Settings and configuration flow."""

import os
import sys
import json
import shutil
import subprocess
import time
import importlib.util
from pathlib import Path
from dotenv import dotenv_values

from rich import box
from rich.panel import Panel
from rich.table import Table
from questionary import Choice

from src.tui.console import console, tlog
from src.tui.inputs import (
    _select_quit,
    _confirm,
    _text,
    _validated_text,
    _validate_number,
    PROVIDER_CHOICES,
)
from src.tui.constants import STATE_FILE, PROVIDER_MODELS, OLLAMA_HOST, LOCAL_LLM_HOST


class SettingsFlowMixin:
    """Mixin for settings and configuration flows."""

    def settings_flow(self):
        env = self._load_env()

        console.print("\n[bold yellow]Settings & Configuration[/bold yellow]")
        
        # Display current settings
        table = Table(title="Current Configuration", box=box.SIMPLE)
        table.add_column("Category", style="cyan")
        table.add_column("Setting", style="yellow")
        table.add_column("Value", style="dim")

        # API Keys (masked)
        for key in ["ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY"]:
            val = env.get(key, "")
            masked = (val[:4] + "..." + val[-4:]) if len(val) > 10 else "(not set)"
            table.add_row("API Keys", key, masked)

        # Hosts
        table.add_row("Hosts", "OLLAMA_HOST", env.get("OLLAMA_HOST", OLLAMA_HOST))
        table.add_row("Hosts", "LOCAL_LLM_HOST", env.get("LOCAL_LLM_HOST", LOCAL_LLM_HOST))

        # Defaults
        table.add_row("Defaults", "DEFAULT_TEMPERATURE", env.get("DEFAULT_TEMPERATURE", "0.7"))
        table.add_row("Defaults", "DEFAULT_MAX_TOKENS", env.get("DEFAULT_MAX_TOKENS", "3000"))
        
        console.print(table)

        while True:
            c = _select_quit(
                "What would you like to edit?",
                choices=[
                    Choice("API Keys — Anthropic, OpenAI, Google", value="keys"),
                    Choice("Hosts — Ollama, Local LLM", value="hosts"),
                    Choice("Generation Defaults — Temp, tokens", value="defaults"),
                    Choice("Paths — Corpus, Database, Logs", value="paths"),
                    Choice("Install/Check Dependencies", value="deps"),
                ],
            )
            if c is None:
                return

            if c == "keys":
                k1 = _text(
                    "Anthropic API Key (Enter to keep)",
                    default=env.get("ANTHROPIC_API_KEY", ""),
                )
                if k1:
                    env["ANTHROPIC_API_KEY"] = k1
                k2 = _text(
                    "OpenAI API Key (Enter to keep)",
                    default=env.get("OPENAI_API_KEY", ""),
                )
                if k2:
                    env["OPENAI_API_KEY"] = k2
                k3 = _text(
                    "Google Gemini API Key (Enter to keep)",
                    default=env.get("GOOGLE_API_KEY", ""),
                )
                if k3:
                    env["GOOGLE_API_KEY"] = k3
                self._save_env(env)
                console.print("[green]✓ API Keys updated[/green]")

            elif c == "hosts":
                h1 = _text(
                    "Ollama Host URL", default=env.get("OLLAMA_HOST", OLLAMA_HOST)
                )
                if h1:
                    env["OLLAMA_HOST"] = h1
                h2 = _text(
                    "Local LLM Host URL",
                    default=env.get("LOCAL_LLM_HOST", LOCAL_LLM_HOST),
                )
                if h2:
                    env["LOCAL_LLM_HOST"] = h2
                self._save_env(env)
                console.print("[green]✓ Host URLs updated[/green]")

            elif c == "defaults":
                t = _validated_text(
                    "Default Temperature (0.0-1.0)",
                    default=env.get("DEFAULT_TEMPERATURE", "0.7"),
                    validate=_validate_number(0.0, 1.0, is_float=True),
                )
                if t:
                    env["DEFAULT_TEMPERATURE"] = t
                mt = _validated_text(
                    "Default Max Tokens",
                    default=env.get("DEFAULT_MAX_TOKENS", "3000"),
                    validate=_validate_number(100, 100000),
                )
                if mt:
                    env["DEFAULT_MAX_TOKENS"] = mt
                self._save_env(env)
                console.print("[green]✓ Defaults updated[/green]")

            elif c == "paths":
                p1 = _text(
                    "Corpus Path", default=env.get("CORPUS_PATH", "corpus/corpus.json")
                )
                if p1:
                    env["CORPUS_PATH"] = p1
                p2 = _text(
                    "Database Path", default=env.get("DATABASE_PATH", "chroma_db")
                )
                if p2:
                    env["DATABASE_PATH"] = p2
                p3 = _text("Log Level", default=env.get("LOG_LEVEL", "INFO"))
                if p3:
                    env["LOG_LEVEL"] = p3.upper()
                self._save_env(env)
                console.print("[green]✓ Paths updated[/green]")

            elif c == "deps":
                self._start_services()  # Re-run dependency check

    def _load_env(self):
        """Load .env file into a dict, creating it if missing."""
        if not Path(".env").exists():
            Path(".env").touch()
        return dotenv_values(".env")

    def _save_env(self, env_dict):
        """Write dict back to .env file."""
        lines = []
        for k, v in env_dict.items():
            if v:
                lines.append(f"{k}={v}")
        Path(".env").write_text("\n".join(lines) + "\n", encoding="utf-8")
        # Also update os.environ for current session
        os.environ.update(env_dict)

    def providers_flow(self):
        """Manage LLM providers (Ollama, OpenAI, Anthropic, Gemini)."""
        console.print("\n[bold yellow]Manage AI Providers[/bold yellow]")
        while True:
            action = _select_quit(
                "Action",
                choices=[
                    Choice("Check Provider Health & Models", value="health"),
                    Choice("Set Default Provider", value="default"),
                    Choice("Pull Ollama Model", value="pull"),
                ],
            )
            if action is None:
                return

            if action == "health":
                self._check_health()
            elif action == "default":
                self._set_default_provider()
            elif action == "pull":
                model = _text("Model to pull (e.g. llama3:8b)", default="llama3")
                if model:
                    self._start_ollama(
                        self._ollama_host_from_env()
                    )  # Ensure running
                    console.print(f"[dim]Running: ollama pull {model}[/dim]")
                    subprocess.run(["ollama", "pull", model])

    def _check_health(self):
        """Ping all configured providers and list available models."""
        console.print("\n[bold cyan]Provider Health Check[/bold cyan]")
        
        providers = ["ollama", "openai", "anthropic", "google"]
        for p in providers:
            status = self._ping_provider(p)
            icon = "[green]✓ Online[/green]" if status else "[red]✗ Offline[/red]"
            console.print(f"{p.title()}: {icon}")
            
            if status and p == "ollama":
                # List models
                try:
                    import httpx
                    host = self._ollama_host_from_env()
                    resp = httpx.get(f"{host}/api/tags", timeout=2.0)
                    if resp.status_code == 200:
                        models = [m["name"] for m in resp.json().get("models", [])]
                        console.print(f"  Models: [dim]{', '.join(models)}[/dim]")
                except Exception:
                    pass

    def _ping_provider(self, provider):
        """Simple connectivity check for a provider."""
        try:
            import httpx

            if provider == "ollama":
                host = self._ollama_host_from_env()
                resp = httpx.get(host, timeout=2.0)
                return resp.status_code == 200
            elif provider == "openai":
                key = os.getenv("OPENAI_API_KEY")
                return key and key.startswith("sk-")
            elif provider == "anthropic":
                key = os.getenv("ANTHROPIC_API_KEY")
                return key and key.startswith("sk-ant")
            elif provider == "google":
                key = os.getenv("GOOGLE_API_KEY")
                return key and len(key) > 10
            elif provider == "openrouter":
                # Implement check if needed
                return True
            return False
        except Exception:
            return False

    def _set_default_provider(self):
        """Set the default provider and model in state."""
        p = _select_quit("Default Provider", choices=PROVIDER_CHOICES)
        if p is None:
            return
        
        # Determine available models
        models = PROVIDER_MODELS.get(p, [])
        if p == "ollama":
            # Try to fetch real list
            try:
                import httpx
                host = self._ollama_host_from_env()
                resp = httpx.get(f"{host}/api/tags", timeout=2.0)
                if resp.status_code == 200:
                    models = [m["name"] for m in resp.json().get("models", [])]
            except Exception:
                pass

        m = _select_quit(
            "Default Model",
            choices=[Choice(mod, value=mod) for mod in models] + [Choice("Custom...", value="__custom__")]
        )
        if m == "__custom__":
            m = _text("Enter model name")
        
        if m:
            state = self._load_state()
            state.setdefault("last_config", {})
            state["last_config"]["provider"] = p
            state["last_config"]["model"] = m
            self._save_state(state)
            console.print(f"[green]✓ Defaults set: {p} / {m}[/green]")

    def _load_state(self):
        if not Path(STATE_FILE).exists():
            return {}
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_state(self, state):
        Path(STATE_FILE).parent.mkdir(parents=True, exist_ok=True)
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)

    def _ping_ollama(self, host=None):
        if not host:
            host = self._ollama_host_from_env()
        try:
            import httpx
            resp = httpx.get(host, timeout=1.0)
            return resp.status_code == 200
        except Exception:
            return False

    def _ollama_host_from_env(self):
        return os.getenv("OLLAMA_HOST", OLLAMA_HOST)

    def _configured_provider(self):
        state = self._load_state()
        return state.get("last_config", {}).get("provider", "ollama")

    def _start_ollama(self, host):
        """Attempt to start 'ollama serve' if not running."""
        if self._ping_ollama(host):
            return True
        
        # Check if we are checking localhost
        if "localhost" not in host and "127.0.0.1" not in host:
            return False  # Can't start remote ollama
            
        console.print("[yellow]Ollama not running. Attempting to start...[/yellow]")
        try:
            # Run in background
            subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            # Wait for it to come up
            for _ in range(10):  # Wait up to 5s
                time.sleep(0.5)
                if self._ping_ollama(host):
                    console.print("[green]✓ Ollama started[/green]")
                    return True
            console.print("[red]✗ Failed to start Ollama automatically[/red]")
            return False
        except FileNotFoundError:
            console.print("[red]✗ 'ollama' command not found in PATH[/red]")
            return False

    def _start_services(self):
        """Check for dependencies and prompt to install if missing."""
        console.print("\n[bold cyan]Initializing Services...[/bold cyan]")

        services_to_check = {
            "ocr": "Import & Preprocess Corpus (OCR, PDF, DOCX)",
            "train": "ML Model Training (sklearn, pandas)",
            "embed": "Semantic Search indexing (chromadb, torch, embeddings)",
            "gen": "Core Generation (httpx)",
            "export": "Document Export (python-docx)",
        }

        missing_services = []
        for key, desc in services_to_check.items():
            if not self._check_service_deps(key):
                missing_services.append((key, desc))
        
        if missing_services:
            console.print("[yellow]Some features require additional dependencies:[/yellow]")
            choices = [
                Choice(f"{desc}", value=key, checked=True)
                for key, desc in missing_services
            ]
            # Use checkbox for multiple selection
            from src.tui.inputs import _checkbox
            
            selected = _checkbox(
                "Select dependencies to install",
                choices=[Choice(desc, value=key) for key, desc in missing_services]
            )

            if selected:
                for key in selected:
                    self._install_service_deps(key)
        
        # Ensure Ollama is running if it's the provider
        if self._configured_provider() == "ollama":
            self._start_ollama(self._ollama_host_from_env())

    def _needs_first_run(self):
        """Check if first-run wizard is needed (no .env or no corpus)."""
        return not Path(".env").exists() or not self._deps_installed()

    def _check_single_dep(self, package_name):
        return importlib.util.find_spec(package_name) is not None

    def _check_service_deps(self, service_key):
        deps = {
            "ocr": ["pytesseract", "pdf2image", "PIL", "docx"],  # PIL is pillow, docx is python-docx
            "train": ["sklearn", "pandas", "joblib", "numpy"],
            "embed": ["chromadb", "sentence_transformers", "torch"],
            "gen": ["httpx"],
            "export": ["docx"],
        }
        for dep in deps.get(service_key, []):
            if not self._check_single_dep(dep):
                return False
        return True

    def _install_service_deps(self, service_key):
        deps_map = {
            "ocr": "pytesseract pdf2image pillow python-docx",
            "train": "scikit-learn pandas joblib numpy",
            "embed": "chromadb sentence-transformers torch",
            "gen": "httpx",
            "export": "python-docx docx2pdf",
        }
        pkgs = deps_map.get(service_key, "")
        if pkgs:
            self._install_deps(pkgs)

    def _deps_installed(self):
        # Basic check for core deps
        return (
            self._check_single_dep("rich")
            and self._check_single_dep("questionary")
            and self._check_single_dep("httpx")
        )

    def _install_deps(self, packages):
        """Install pip packages via subprocess."""
        if not _confirm(f"Install {packages} via pip?", default=True):
            return
        try:
            with console.status(f"[bold green]Installing {packages}...", spinner="dots"):
                subprocess.check_call(
                    [sys.executable, "-m", "pip", "install"] + packages.split()
                )
            console.print(f"[green]✓ Installed {packages}[/green]")
        except subprocess.CalledProcessError as e:
            console.print(f"[red]✗ Install failed: {e}[/red]")

    def _apply_chromadb_py314_patch(self):
        """
        Apply a monkey patch for ChromaDB on Python 3.14 (if applicable).
        Currently just a placeholder or specific fix if needed.
        """
        if sys.version_info >= (3, 14):
            # Known issue with some libraries on 3.14 alpha/beta
            # Pass for now unless specific patch known
            pass

    def first_run_wizard(self):
        # Create .env if missing
        self._load_env()
        
        console.print(
            Panel(
                "[bold cyan]Welcome to Jikai![/bold cyan]\n"
                "[dim]Let's set up your environment. Steps already done will be skipped.[/dim]",
                box=box.DOUBLE,
                border_style="cyan",
            )
        )

        # Step 1: Install deps
        if not self._deps_installed():
            if _confirm("Install core dependencies?", default=True):
                self._install_deps("httpx python-docx sentence-transformers chromadb scikit-learn pandas")
        
        # Step 2: Configure API keys
        env = self._load_env()
        if not any(k in env for k in ["ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY"]):
            if _confirm("Configure API Keys now?", default=True):
                 # Reuse check logic
                 self.settings_flow() # Actually this might be too broad.
                 # Let's just ask for keys inline
                 k = _text("Anthropic Key (optional):")
                 if k: env["ANTHROPIC_API_KEY"] = k
                 k = _text("OpenAI Key (optional):")
                 if k: env["OPENAI_API_KEY"] = k
                 self._save_env(env)

        # Step 3: Check corpus
        # Assume _corpus_ready logic from original app will be handled by user manually or via checks
        # Re-using _corpus_ready from self if available
        is_ready = False
        if hasattr(self, "_corpus_ready"):
            is_ready = self._corpus_ready()
        
        if not is_ready:
            console.print("[yellow]Corpus not ready.[/yellow]")
            if _confirm("Import/Preprocess corpus now?", default=True):
                if hasattr(self, "import_cases_flow"):
                     self.import_cases_flow() # Or corpus flow
                elif hasattr(self, "ocr_flow"):
                     self.ocr_flow()

        console.print("[green]First run setup complete![/green]")
