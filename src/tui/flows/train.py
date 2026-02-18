"""ML training and embedding flow."""

import json
from pathlib import Path
from typing import Optional

from rich import box
from rich.panel import Panel
from rich.table import Table
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from questionary import Choice

from src.tui.console import console, tlog
from src.tui.inputs import (
    _path,
    _checkbox,
    _validated_text,
    _validate_number,
    _confirm,
)
from src.tui.utils import run_async


class TrainFlowMixin:
    """Mixin for training and embedding flows."""

    def train_flow(self):
        console.print("\n[bold yellow]Train ML Models[/bold yellow]")
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

        # Early exit if no models selected
        if not (train_cls or train_reg or train_clu):
            console.print("[yellow]No models selected. Returning to menu.[/yellow]")
            return

        # Defaults for optional parameters
        max_features = "5000"
        test_split = "0.2"
        cls_c = 1.0
        reg_alpha = 1.0
        n_clusters = 5

        # Text vectorization settings (needed for classifier or regressor)
        if train_cls or train_reg:
            console.print("\n[cyan]Text Vectorization Settings[/cyan]")
            max_features = _validated_text(
                "Max features (vocabulary size)",
                default="5000",
                validate=_validate_number(1, 100000),
            )
            if max_features is None:
                return

            test_split = _validated_text(
                "Test split ratio",
                default="0.2",
                validate=_validate_number(0.0, 1.0, is_float=True),
            )
            if test_split is None:
                return

        # Classifier-specific options
        if train_cls:
            console.print("\n[cyan]Classifier Settings[/cyan]")
            cls_c_str = _validated_text(
                "Classifier regularization (C, higher=less regularization)",
                default="1.0",
                validate=_validate_number(0.001, 1000.0, is_float=True),
            )
            if cls_c_str is None:
                return
            cls_c = float(cls_c_str)

        # Regressor-specific options
        if train_reg:
            console.print("\n[cyan]Regressor Settings[/cyan]")
            reg_alpha_str = _validated_text(
                "Regressor regularization (alpha, higher=more regularization)",
                default="1.0",
                validate=_validate_number(0.0001, 1000.0, is_float=True),
            )
            if reg_alpha_str is None:
                return
            reg_alpha = float(reg_alpha_str)

        # Clustering-specific options (only ask if clustering is selected)
        if train_clu:
            console.print("\n[cyan]Clusterer Settings[/cyan]")
            n_clusters_str = _validated_text(
                "Number of clusters",
                default="5",
                validate=_validate_number(2, 100),
            )
            if n_clusters_str is None:
                return
            n_clusters = int(n_clusters_str)

        cfg = Table(box=box.SIMPLE, title="Training Config")
        cfg.add_column("Parameter", style="cyan")
        cfg.add_column("Value", style="yellow")
        cfg.add_row("Data Path", data_path)
        if train_cls or train_reg:
            cfg.add_row("Max Features", max_features)
            cfg.add_row("Test Split", test_split)
        if train_cls:
            cfg.add_row("Classifier", f"Yes (C={cls_c})")
        if train_reg:
            cfg.add_row("Regressor", f"Yes (alpha={reg_alpha})")
        if train_clu:
            cfg.add_row("Clusterer", f"Yes ({n_clusters} clusters)")
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
        self._do_train(
            data_path,
            int(max_features),
            float(test_split),
            train_cls,
            cls_c,
            train_reg,
            reg_alpha,
            train_clu,
            n_clusters,
        )

    def _do_train(self, data_path, max_features, test_split, train_cls, cls_c, train_reg, reg_alpha, train_clu, n_clusters):
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
                    n_clusters=n_clusters if train_clu else 5,
                    max_features=max_features,
                )
                # Note: cls_c, reg_alpha, test_split are available for future pipeline enhancements
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

    def embed_flow(self):
        console.print("\n[bold yellow]Generate Embeddings (ChromaDB)[/bold yellow]")
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
                    run_async(vs.index_hypotheticals(batch))
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
