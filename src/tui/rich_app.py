"""Jikai Rich TUI - Procedural terminal interface (caipng-style)."""

import asyncio
import csv
import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional

import questionary
from questionary import Choice
from rich import box
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table
from rich.text import Text

console = Console()
LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_PATH = os.path.join(LOG_DIR, "tui.log")
_fh = logging.FileHandler(LOG_PATH, mode="w", encoding="utf-8")
_fh.setFormatter(
    logging.Formatter("%(asctime)s  %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
)
tlog = logging.getLogger("jikai.tui")
tlog.setLevel(logging.INFO)
tlog.addHandler(_fh)

TOPICS = [
    "negligence",
    "duty_of_care",
    "causation",
    "remoteness",
    "battery",
    "assault",
    "false_imprisonment",
    "defamation",
    "private_nuisance",
    "trespass_to_land",
    "vicarious_liability",
    "strict_liability",
    "harassment",
    "occupiers_liability",
    "product_liability",
    "contributory_negligence",
    "economic_loss",
    "psychiatric_harm",
    "employers_liability",
]
PROVIDERS = ["ollama", "openai", "anthropic", "google", "local"]


def _topic_choices():
    return [Choice(t.replace("_", " ").title(), value=t) for t in TOPICS]


COMPLEXITY_CHOICES = [
    Choice("1 — Simple", value="1"),
    Choice("2 — Basic", value="2"),
    Choice("3 — Moderate", value="3"),
    Choice("4 — Complex", value="4"),
    Choice("5 — Advanced", value="5"),
]
PARTIES_CHOICES = [
    Choice("2 parties", value="2"),
    Choice("3 parties", value="3"),
    Choice("4 parties", value="4"),
    Choice("5 parties", value="5"),
]
METHOD_CHOICES = [
    Choice("Pure LLM", value="pure_llm"),
    Choice("ML Assisted", value="ml_assisted"),
    Choice("Hybrid", value="hybrid"),
]
PROVIDER_CHOICES = [
    Choice("Ollama (local)", value="ollama"),
    Choice("OpenAI", value="openai"),
    Choice("Anthropic", value="anthropic"),
    Choice("Google", value="google"),
    Choice("Local LLM", value="local"),
]
PROVIDER_MODELS = {
    "ollama": ["llama3", "llama3.1", "mistral", "gemma2", "phi3", "codellama", "qwen2"],
    "openai": [
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4-turbo",
        "gpt-3.5-turbo",
        "o1",
        "o1-mini",
    ],
    "anthropic": [
        "claude-sonnet-4-5-20250929",
        "claude-opus-4-20250918",
        "claude-haiku-4-5-20251001",
        "claude-3-5-sonnet-20241022",
    ],
    "google": ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"],
    "local": ["default"],
}


def _model_choices(provider):
    choices = [Choice(m, value=m) for m in PROVIDER_MODELS.get(provider, [])]
    choices.append(Choice("Custom...", value="__custom__"))
    return choices


def _select(message, choices):
    """Arrow-key select menu. Returns value or None on Ctrl+C."""
    try:
        return questionary.select(message, choices=choices).ask()
    except KeyboardInterrupt:
        return None


def _select_quit(message, choices):
    """Arrow-key select with q-to-quit keybinding. Returns value or None."""
    from prompt_toolkit.key_binding import KeyBindings, merge_key_bindings

    kb = KeyBindings()

    @kb.add("q")
    def _quit_on_q(event):
        event.app.exit(exception=KeyboardInterrupt())

    try:
        q = questionary.select(message, choices=choices, instruction="(q to quit)")
        orig = q.application.key_bindings
        q.application.key_bindings = merge_key_bindings([orig, kb]) if orig else kb
        return q.unsafe_ask()
    except (KeyboardInterrupt, EOFError):
        return None


def _checkbox(message, choices):
    """Arrow-key checkbox menu. Returns list or None on Ctrl+C."""
    try:
        return questionary.checkbox(message, choices=choices).ask()
    except KeyboardInterrupt:
        return None


def _text(message, default=""):
    """questionary text input with default."""
    try:
        return questionary.text(message, default=default).ask()
    except KeyboardInterrupt:
        return None


def _password(message, default=""):
    """questionary password input (masked)."""
    try:
        return questionary.password(message, default=default).ask()
    except KeyboardInterrupt:
        return None


def _confirm(message, default=True):
    """questionary yes/no confirm."""
    try:
        return questionary.confirm(message, default=default).ask()
    except KeyboardInterrupt:
        return False


def _path(message, default=""):
    """questionary path input with autocomplete."""
    try:
        return questionary.path(message, default=default).ask()
    except KeyboardInterrupt:
        return None


def _validate_number(min_val, max_val, is_float=False):
    """Return a questionary validator for numeric range."""

    def _validator(val):
        try:
            n = float(val) if is_float else int(val)
        except (ValueError, TypeError):
            kind = "float" if is_float else "integer"
            return f"Must be a valid {kind}"
        if n < min_val or n > max_val:
            return f"Must be between {min_val} and {max_val}"
        return True

    return _validator


def _validated_text(message, default="", validate=None):
    """questionary text with validation."""
    try:
        return questionary.text(message, default=default, validate=validate).ask()
    except KeyboardInterrupt:
        return None


def _run_async(coro):
    """Run async coroutine from synchronous context."""
    return asyncio.run(coro)


class JikaiTUI:
    def __init__(self):
        self._loaded_path = ""
        self._entries: list = []
        self._corpus_path = "corpus/clean/tort/corpus.json"
        self._raw_dir = "corpus/raw"
        self._models_dir = "models"
        self._train_data = "corpus/labelled/sample.csv"

    def display_banner(self):
        tlog.info("=== TUI session started ===")
        console.print(
            Panel(
                "[bold cyan]Jikai - Legal Hypothetical Generator[/bold cyan]\n"
                "[dim]AI-powered Singapore tort law hypothetical generation[/dim]",
                box=box.DOUBLE,
                border_style="cyan",
            )
        )

    def _corpus_ready(self):
        return Path(self._corpus_path).exists()

    def _labelled_ready(self):
        return Path(self._train_data).exists()

    def _models_ready(self):
        md = Path(self._models_dir)
        return all(
            (md / f).exists()
            for f in ("classifier.joblib", "vectorizer.joblib", "binarizer.joblib")
        )

    def _embeddings_ready(self):
        return Path("chroma_db").exists() and any(Path("chroma_db").iterdir())

    def main_menu(self):
        while True:
            console.print("\n[bold yellow]Main Menu[/bold yellow]")
            corpus_ok = self._corpus_ready()
            labelled_ok = self._labelled_ready()
            models_ok = self._models_ready()
            embed_ok = self._embeddings_ready()
            c_tag = "✓" if corpus_ok else "✗"
            l_tag = "✓" if labelled_ok else "✗"
            m_tag = "✓" if models_ok else "✗"
            e_tag = "✓" if embed_ok else "✗"
            browse_disabled = None if corpus_ok else "preprocess corpus first"
            label_disabled = None if corpus_ok else "preprocess corpus first"
            train_disabled = None if labelled_ok else "label corpus first"
            embed_disabled = None if corpus_ok else "preprocess corpus first"
            gen_disabled = None if corpus_ok else "preprocess corpus first"
            choice = _select_quit(
                "Select (workflow: 1 → 1a/1b → 2/2a → 3)",
                choices=[
                    Choice(f"1.  OCR / Preprocess Corpus {c_tag}", value="ocr"),
                    Choice(
                        "  1a. Browse Corpus", value="corpus", disabled=browse_disabled
                    ),
                    Choice(
                        f"  1b. Label Corpus {l_tag}",
                        value="label",
                        disabled=label_disabled,
                    ),
                    Choice(
                        f"2.  Train ML Models (optional) {m_tag}",
                        value="train",
                        disabled=train_disabled,
                    ),
                    Choice(
                        f"  2a. Generate Embeddings (optional) {e_tag}",
                        value="embed",
                        disabled=embed_disabled,
                    ),
                    Choice(
                        "3.  Generate Hypothetical", value="gen", disabled=gen_disabled
                    ),
                    Choice("Settings", value="settings"),
                    Choice("Providers", value="providers"),
                ],
            )
            if choice is None:
                console.print("[dim]Goodbye.[/dim]")
                tlog.info("=== TUI session ended ===")
                break
            if choice == "ocr":
                self.ocr_flow()
            elif choice == "corpus":
                self.corpus_flow()
            elif choice == "label":
                self.label_flow()
            elif choice == "train":
                self.train_flow()
            elif choice == "embed":
                self.embed_flow()
            elif choice == "gen":
                self.generate_flow()
            elif choice == "settings":
                self.settings_flow()
            elif choice == "providers":
                self.providers_flow()

    # ── ocr / preprocess ──────────────────────────────────────
    def ocr_flow(self):
        console.print("\n[bold yellow]OCR / Preprocess Corpus[/bold yellow]")
        console.print("=" * 60)
        while True:
            c = _select(
                "OCR Menu",
                choices=[
                    Choice("Preprocess raw corpus (TXT/PDF/PNG/DOCX)", value="1"),
                    Choice("Convert single file to TXT (OCR)", value="2"),
                    Choice("Back", value="3"),
                ],
            )
            if c is None:
                c = "3"
            if c == "1":
                self._preprocess_raw()
            elif c == "2":
                self._ocr_single()
            elif c == "3":
                return

    def _ocr_single(self):
        path = _path("File to OCR (PDF/PNG/JPG/DOCX)", default="")
        if not path:
            return
        try:
            from ..services.corpus_preprocessor import extract_text, normalize_text

            with console.status("[bold green]Extracting text...", spinner="dots"):
                text = normalize_text(extract_text(Path(path)))
            if not text:
                console.print("[red]✗ No text extracted (check file format/deps)[/red]")
                return
            console.print(
                Panel(
                    text[:2000] + ("..." if len(text) > 2000 else ""),
                    title=f"Extracted from {Path(path).name}",
                    box=box.ROUNDED,
                    border_style="green",
                )
            )
            out = _path("Save TXT to (enter to skip)", default="")
            if out:
                Path(out).write_text(text, encoding="utf-8")
                console.print(f"[green]✓ Saved to {out}[/green]")
            tlog.info("OCR  %s → %d chars", path, len(text))
        except Exception as e:
            console.print(f"[red]✗ OCR failed: {e}[/red]")
            console.print(
                "[dim]Tip: ensure pytesseract and tesseract are installed[/dim]"
            )

    # ── label ──────────────────────────────────────────────────
    def label_flow(self):
        console.print("\n[bold yellow]Label Corpus → Training CSV[/bold yellow]")
        console.print("=" * 60)
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
            action = _select(
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
            difficulty = _select("Difficulty", choices=difficulty_choices)
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
            console.print(f"[green]✓ Labelled ({count} this session)[/green]")
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

    # ── generate ────────────────────────────────────────────────
    def generate_flow(self):
        while True:
            console.print("\n[bold yellow]Generate Hypothetical[/bold yellow]")
            console.print("=" * 60)
            topic = _select("Topic", choices=_topic_choices())
            if topic is None:
                return
            provider = _select("Provider", choices=PROVIDER_CHOICES)
            if provider is None:
                return
            model_name = _select("Model", choices=_model_choices(provider))
            if model_name is None:
                return
            if model_name == "__custom__":
                model_name = _text("Custom model name", default="")
                if model_name is None:
                    return
            temperature = _select(
                "Temperature",
                choices=[
                    Choice(f"{v/10:.1f}", value=str(v / 10))
                    for v in range(1, 16)
                ],
            )
            if temperature is None:
                return
            temperature = float(temperature)
            complexity = _select("Complexity", choices=COMPLEXITY_CHOICES)
            if complexity is None:
                return
            parties = _select("Parties", choices=PARTIES_CHOICES)
            if parties is None:
                return
            method = _select("Method", choices=METHOD_CHOICES)
            if method is None:
                return
            cfg = Table(box=box.SIMPLE, title="Generation Config")
            cfg.add_column("Parameter", style="cyan")
            cfg.add_column("Value", style="yellow")
            cfg.add_row("Topic", topic)
            cfg.add_row("Provider", provider)
            cfg.add_row("Model", model_name or "(default)")
            cfg.add_row("Temperature", f"{temperature:.1f}")
            cfg.add_row("Complexity", complexity)
            cfg.add_row("Parties", parties)
            cfg.add_row("Method", method)
            console.print(cfg)
            if not _confirm("Proceed with generation?", default=True):
                return
            tlog.info(
                "GENERATE  topic=%s provider=%s model=%s temp=%.1f "
                "complexity=%s parties=%s method=%s",
                topic,
                provider,
                model_name,
                temperature,
                complexity,
                parties,
                method,
            )
            self._do_generate(
                topic,
                provider,
                model_name or None,
                int(complexity),
                int(parties),
                method,
                temperature,
            )
            if not _confirm("Generate another?", default=False):
                return

    def _do_generate(self, topic, provider, model, complexity, parties, method, temperature=0.7):
        max_retries = 3
        try:
            from ..services.llm_service import LLMRequest, llm_service
            from ..services.validation_service import validation_service

            request = LLMRequest(
                prompt=(
                    f"Generate a Singapore tort law hypothetical about "
                    f"{topic} with {parties} parties at complexity "
                    f"{complexity}/5."
                ),
                temperature=temperature,
                stream=True,
            )

            async def _stream():
                chunks: List[str] = []
                with Live(
                    Text("Generating..."), console=console, refresh_per_second=4
                ) as live:
                    async for chunk in llm_service.stream_generate(
                        request, provider=provider, model=model
                    ):
                        chunks.append(chunk)
                        live.update(Text("".join(chunks)))
                return "".join(chunks)

            try:
                console.print("[dim]Attempt 1/{0}[/dim]".format(max_retries))
                result = _run_async(_stream())
                if result:
                    vr = validation_service.validate_hypothetical(
                        text=result,
                        required_topics=[topic],
                        expected_parties=parties,
                    )
                    score = vr.get("overall_score", 0.0)
                    passed = vr.get("passed", False)
                    console.print(
                        Panel(
                            result,
                            title="Generated Hypothetical",
                            box=box.ROUNDED,
                            border_style="green",
                        )
                    )
                    self._show_validation(vr)
                    if passed or score >= 7.0:
                        tlog.info(
                            "GENERATE  stream success, len=%d score=%.1f",
                            len(result),
                            score,
                        )
                        return
                    console.print(
                        f"[yellow]Score {score:.1f}/10 < 7.0, retrying with full generation...[/yellow]"
                    )
            except Exception as stream_err:
                tlog.info("GENERATE  stream failed: %s, trying full", stream_err)
                console.print(
                    "[yellow]Stream unavailable "
                    f"({stream_err}), using full generation...[/yellow]"
                )

            from ..services.hypothetical_service import (
                GenerationRequest,
                hypothetical_service,
            )

            feedback = ""
            for attempt in range(1, max_retries + 1):
                console.print(
                    f"[dim]Attempt {attempt}/{max_retries} (full generation)[/dim]"
                )

                async def _full(extra_feedback=feedback):
                    prefs = {"temperature": temperature}
                    if extra_feedback:
                        prefs["feedback"] = extra_feedback
                    req = GenerationRequest(
                        topics=[topic],
                        number_parties=max(2, min(5, parties)),
                        complexity_level=str(complexity),
                        method=method,
                        provider=provider,
                        model=model,
                        user_preferences=prefs,
                    )
                    return await hypothetical_service.generate_hypothetical(req)

                with console.status(
                    f"[bold green]Generating hypothetical (attempt {attempt}/{max_retries})...",
                    spinner="dots",
                ):
                    response = _run_async(_full(feedback))

                console.print(
                    Panel(
                        response.hypothetical,
                        title=f"Generated Hypothetical (attempt {attempt})",
                        box=box.ROUNDED,
                        border_style="green",
                    )
                )
                if response.analysis:
                    console.print(
                        Panel(
                            response.analysis,
                            title="Legal Analysis",
                            box=box.ROUNDED,
                            border_style="cyan",
                        )
                    )
                vr = response.validation_results
                self._show_validation(vr)
                score = vr.get("quality_score", 0.0)
                passed = vr.get("passed", False)
                if passed or score >= 7.0:
                    tlog.info(
                        "GENERATE  full success attempt=%d score=%.1f",
                        attempt,
                        score,
                    )
                    return

                if attempt < max_retries:
                    # Build feedback for next attempt
                    checks = vr.get("checks", vr.get("adherence_check", {}).get("checks", {}))
                    issues = []
                    if isinstance(checks, dict):
                        if not checks.get("party_count", {}).get("passed", True):
                            issues.append(
                                f"Include exactly {parties} distinct named parties."
                            )
                        if not checks.get("topic_inclusion", {}).get("passed", True):
                            missing = checks.get("topic_inclusion", {}).get(
                                "topics_missing", []
                            )
                            if missing:
                                issues.append(
                                    f"Must address these topics: {', '.join(missing)}."
                                )
                        if not checks.get("word_count", {}).get("passed", True):
                            issues.append("Aim for 800-1500 words.")
                        if not checks.get("singapore_context", {}).get("passed", True):
                            issues.append(
                                "Set the scenario explicitly in Singapore."
                            )
                    feedback = (
                        "Previous attempt scored {:.1f}/10. Fix these issues: {}".format(
                            score, " ".join(issues) if issues else "Improve overall quality."
                        )
                    )
                    console.print(
                        f"[yellow]Score {score:.1f}/10 < 7.0, retrying...[/yellow]"
                    )

            console.print(
                "[yellow]Max retries reached. Showing best result above.[/yellow]"
            )
            tlog.info("GENERATE  max retries reached, score=%.1f", score)
        except Exception as e:
            console.print(f"[red]✗ Generation failed: {e}[/red]")
            console.print("[dim]Tip: check provider health via Providers menu[/dim]")
            tlog.info("ERROR  generation: %s", e)

    def _show_validation(self, vr):
        """Display validation results table."""
        if not vr:
            return
        vt = Table(title="Validation Results", box=box.ROUNDED)
        vt.add_column("Check", style="cyan")
        vt.add_column("Result", style="yellow")
        vt.add_row("Quality Score", str(vr.get("quality_score", "N/A")))
        vt.add_row(
            "Passed",
            "[green]Yes[/green]" if vr.get("passed") else "[red]No[/red]",
        )
        console.print(vt)

    # ── train ───────────────────────────────────────────────────
    def train_flow(self):
        console.print("\n[bold yellow]Train ML Models[/bold yellow]")
        console.print("=" * 60)
        console.print(
            "[dim]All models are optional — generation works without them.\n"
            "Trained models enrich output with quality checks and topic alignment.[/dim]\n"
        )
        info = Table(box=box.SIMPLE, title="Model Reference")
        info.add_column("Model", style="cyan")
        info.add_column("Purpose", style="yellow")
        info.add_column("Required?", style="dim")
        info.add_row("Classifier", "Predicts legal topics in generated text", "No")
        info.add_row("Regressor", "Scores hypothetical quality (0-10)", "No")
        info.add_row("Clusterer", "Groups similar hypotheticals for diversity", "No")
        console.print(info)
        data_path = _path(
            "Training data path (labelled CSV)",
            default=self._train_data,
        )
        if data_path is None:
            return
        models = _checkbox(
            "Select models to train",
            choices=[
                Choice("Classifier — topic prediction", value="cls", checked=True),
                Choice("Regressor — quality scoring", value="reg", checked=True),
                Choice("Clusterer — diversity grouping", value="clu", checked=True),
            ],
        )
        if models is None:
            return
        train_cls = "cls" in models
        train_reg = "reg" in models
        train_clu = "clu" in models
        n_clusters = _validated_text(
            "Number of clusters",
            default="5",
            validate=_validate_number(1, 1000),
        )
        if n_clusters is None:
            return
        test_split = _validated_text(
            "Test split",
            default="0.2",
            validate=_validate_number(0.0, 1.0, is_float=True),
        )
        if test_split is None:
            return
        max_features = _validated_text(
            "Max features",
            default="5000",
            validate=_validate_number(1, 100000),
        )
        if max_features is None:
            return
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
        if not _confirm("Proceed with training?", default=True):
            return
        tlog.info(
            "TRAIN  data=%s cls=%s reg=%s clu=%s",
            data_path,
            train_cls,
            train_reg,
            train_clu,
        )
        self._do_train(data_path, int(n_clusters), int(max_features))

    def _do_train(self, data_path, n_clusters, max_features):
        try:
            from ..ml.pipeline import MLPipeline

            pipeline = MLPipeline()
            stages = {
                "data": "Loading data",
                "features": "Extracting TF-IDF features",
                "classifier": "Training classifier — topic prediction",
                "regressor": "Training regressor — quality scoring",
                "clusterer": "Training clusterer — diversity grouping",
                "saving": "Saving models to disk",
            }
            stage_thresholds = [
                (0.05, "data"),
                (0.15, "features"),
                (0.25, "classifier"),
                (0.50, "regressor"),
                (0.75, "clusterer"),
                (0.90, "saving"),
            ]
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeElapsedColumn(),
                console=console,
            ) as progress:
                tasks = {}
                for key, label in stages.items():
                    tasks[key] = progress.add_task(f"[dim]{label}", total=100)
                current_stage: Optional[str] = None

                def on_progress(pct, msg):
                    nonlocal current_stage
                    for threshold, stage_key in stage_thresholds:
                        if pct >= threshold and stage_key != current_stage:
                            if current_stage is not None and current_stage in tasks:
                                progress.update(
                                    tasks[current_stage],
                                    completed=100,
                                    description=f"[green]✓ {stages[current_stage]}",
                                )
                            current_stage = stage_key
                            progress.update(
                                tasks[stage_key],
                                completed=50,
                                description=f"[cyan]⧗ {stages[stage_key]}",
                            )
                    overall_pct = int(pct * 100)
                    if current_stage:
                        progress.update(
                            tasks[current_stage], completed=min(95, overall_pct)
                        )

                metrics = pipeline.train_all(
                    data_path,
                    progress_callback=on_progress,
                    n_clusters=n_clusters,
                    max_features=max_features,
                )
                for key in tasks:
                    progress.update(
                        tasks[key],
                        completed=100,
                        description=f"[green]✓ {stages[key]}",
                    )
            console.print("\n[bold green]✓ Training Complete![/bold green]")
            mt = Table(title="Training Metrics", box=box.ROUNDED)
            mt.add_column("Model", style="cyan")
            mt.add_column("Metrics", style="yellow")
            for name, vals in metrics.items():
                mt.add_row(name, str(vals))
            console.print(mt)
            tlog.info("TRAIN  complete")
        except Exception as e:
            console.print(f"[red]✗ Training failed: {e}[/red]")
            console.print(
                "[dim]Tip: ensure training CSV exists at specified path[/dim]"
            )
            tlog.info("ERROR  training: %s", e)

    # ── embeddings ──────────────────────────────────────────────
    def embed_flow(self):
        console.print("\n[bold yellow]Generate Embeddings (ChromaDB)[/bold yellow]")
        console.print("=" * 60)
        console.print(
            "[dim]Indexes corpus into ChromaDB using sentence-transformers.\n"
            "Enables semantic search during hypothetical generation.\n"
            "Optional — generation falls back to keyword matching without embeddings.[/dim]\n"
        )
        corpus_path = _path("Corpus JSON to index", default=self._corpus_path)
        if corpus_path is None:
            return
        if not Path(corpus_path).exists():
            console.print(f"[red]✗ File not found: {corpus_path}[/red]")
            return
        if not _confirm(f"Index {corpus_path} into ChromaDB?", default=True):
            return
        try:
            with open(corpus_path) as f:
                data = json.load(f)
            entries = data if isinstance(data, list) else data.get("entries", [])
            if not entries:
                console.print("[red]✗ No entries in corpus[/red]")
                return
            from ..services.vector_service import VectorService

            hypos = []
            for i, e in enumerate(entries):
                text = e.get("text", "")
                topics = e.get("topic", e.get("topics", []))
                if isinstance(topics, str):
                    topics = [t.strip() for t in topics.split(",")]
                hypos.append(
                    {
                        "id": f"entry_{i}",
                        "text": text,
                        "topics": topics,
                        "metadata": e.get("metadata", {}),
                    }
                )
            vs = VectorService()
            if not vs._initialized:
                console.print("[red]✗ Vector service failed to initialize[/red]")
                console.print(
                    "[dim]Tip: ensure chromadb and sentence-transformers are installed[/dim]"
                )
                return
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeElapsedColumn(),
                console=console,
            ) as progress:
                task = progress.add_task(
                    "[cyan]Generating embeddings", total=len(hypos)
                )
                batch_size = 20
                for start in range(0, len(hypos), batch_size):
                    batch = hypos[start : start + batch_size]
                    _run_async(vs.index_hypotheticals(batch))
                    progress.update(task, advance=len(batch))
            console.print(
                f"[green]✓ Indexed {len(hypos)} entries into ChromaDB[/green]"
            )
            tlog.info("EMBED  %d entries indexed", len(hypos))
        except Exception as e:
            console.print(f"[red]✗ Embedding failed: {e}[/red]")
            console.print(
                "[dim]Tip: check sentence-transformers and chromadb deps[/dim]"
            )
            tlog.info("ERROR  embedding: %s", e)

    # ── corpus ──────────────────────────────────────────────────
    def corpus_flow(self):
        console.print("\n[bold yellow]Browse Corpus[/bold yellow]")
        console.print("=" * 60)
        path = _path(
            "Corpus file path",
            default=self._corpus_path,
        )
        if path is None:
            return
        self._load_corpus(path)
        while True:
            c = _select(
                "Corpus Menu",
                choices=[
                    Choice("View entry", value="1"),
                    Choice("Search", value="2"),
                    Choice("Filter by topic", value="3"),
                    Choice("Export CSV", value="4"),
                    Choice("Export JSON", value="5"),
                    Choice("Preprocess raw", value="6"),
                    Choice("Load different file", value="7"),
                    Choice("Back", value="8"),
                ],
            )
            if c is None:
                c = "8"
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
            elif c == "8":
                return

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
            pick = _select(f"Page {page+1} ({end}/{len(entries)})", choices=nav)
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
        topic = _select("Filter topic", choices=_topic_choices())
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

    # ── settings ────────────────────────────────────────────────
    def settings_flow(self):
        console.print("\n[bold yellow]Settings[/bold yellow]")
        console.print("=" * 60)
        env = self._load_env()

        def _mask(v):
            if not v:
                return ""
            return v[:4] + "****" + v[-4:] if len(v) > 8 else "****"

        anthropic_key = _password(
            f"Anthropic API Key ({_mask(env.get('ANTHROPIC_API_KEY', ''))})",
            default=env.get("ANTHROPIC_API_KEY", ""),
        )
        if anthropic_key is None:
            return
        openai_key = _password(
            f"OpenAI API Key ({_mask(env.get('OPENAI_API_KEY', ''))})",
            default=env.get("OPENAI_API_KEY", ""),
        )
        if openai_key is None:
            return
        google_key = _password(
            f"Google API Key ({_mask(env.get('GOOGLE_API_KEY', ''))})",
            default=env.get("GOOGLE_API_KEY", ""),
        )
        if google_key is None:
            return
        ollama_host = _text(
            "Ollama Host",
            default=env.get("OLLAMA_HOST", "http://localhost:11434"),
        )
        if ollama_host is None:
            return
        local_host = _text(
            "Local LLM Host",
            default=env.get("LOCAL_LLM_HOST", "http://localhost:8080"),
        )
        if local_host is None:
            return
        temperature = _validated_text(
            "Default Temperature",
            default=env.get("DEFAULT_TEMPERATURE", "0.7"),
            validate=_validate_number(0.0, 2.0, is_float=True),
        )
        if temperature is None:
            return
        max_tokens = _validated_text(
            "Default Max Tokens",
            default=env.get("DEFAULT_MAX_TOKENS", "2048"),
            validate=_validate_number(1, 100000),
        )
        if max_tokens is None:
            return
        corpus_path = _path(
            "Corpus Path",
            default=env.get("CORPUS_PATH", self._corpus_path),
        )
        if corpus_path is None:
            return
        db_path = _path(
            "Database Path",
            default=env.get("DATABASE_PATH", "data/jikai.db"),
        )
        if db_path is None:
            return
        log_level = _select("Log Level", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
        if log_level is None:
            return
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
        if not _confirm("Save settings to .env?", default=True):
            return
        lines = [
            f"ANTHROPIC_API_KEY={anthropic_key}",
            f"OPENAI_API_KEY={openai_key}",
            f"GOOGLE_API_KEY={google_key}",
            f"OLLAMA_HOST={ollama_host}",
            f"LOCAL_LLM_HOST={local_host}",
            f"DEFAULT_TEMPERATURE={temperature}",
            f"DEFAULT_MAX_TOKENS={max_tokens}",
            f"CORPUS_PATH={corpus_path}",
            f"DATABASE_PATH={db_path}",
            f"LOG_LEVEL={log_level}",
        ]
        with open(".env", "w") as f:
            f.write("\n".join(lines) + "\n")
        console.print("[green]✓ Settings saved to .env[/green]")
        tlog.info("SETTINGS  saved")

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
            c = _select(
                "Providers",
                choices=[
                    Choice("Check Health", value="1"),
                    Choice("Set Default Provider", value="2"),
                    Choice("Back", value="3"),
                ],
            )
            if c is None:
                c = "3"
            if c == "1":
                self._check_health()
            elif c == "2":
                self._set_default_provider()
            elif c == "3":
                return

    def _check_health(self):
        try:
            from ..services.llm_service import llm_service

            async def _health():
                h = await llm_service.health_check()
                m = await llm_service.list_models()
                return h, m

            with console.status(
                "[bold green]Checking provider health...", spinner="dots"
            ):
                health, models = _run_async(_health())
            ht = Table(title="Provider Health", box=box.ROUNDED)
            ht.add_column("Provider", style="cyan")
            ht.add_column("Status", style="yellow")
            ht.add_column("Models", style="dim")
            for name, status in health.items():
                healthy = (
                    status.get("healthy", False) if isinstance(status, dict) else status
                )
                icon = "[green]✓[/green]" if healthy else "[red]✗[/red]"
                ml = models.get(name, [])
                ht.add_row(name, icon, ", ".join(ml[:5]) if ml else "-")
            console.print(ht)
            tlog.info("HEALTH  %s", {k: str(v) for k, v in health.items()})
        except Exception as e:
            console.print(f"[red]✗ Health check failed: {e}[/red]")

    def _set_default_provider(self):
        provider = _select("Default provider", choices=PROVIDER_CHOICES)
        if provider is None:
            return
        try:
            from ..services.llm_service import llm_service

            llm_service.select_provider(provider)
            console.print(f"[green]✓ Default provider: {provider}[/green]")
            tlog.info("PROVIDER  default=%s", provider)
        except Exception as e:
            console.print(f"[red]✗ Failed: {e}[/red]")

    # ── entry point ─────────────────────────────────────────────
    def run(self):
        self.display_banner()
        self.main_menu()


if __name__ == "__main__":
    JikaiTUI().run()
