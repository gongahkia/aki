"""Train screen for ML model training."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.screen import Screen
from textual.widgets import (
    Checkbox,
    Footer,
    Header,
    Input,
    Label,
    ProgressBar,
    Static,
)

SCREEN_CSS = """
TrainScreen {
    layout: vertical;
    background: #ffffff;
    color: #1a1a1a;
}
#train-form { height: auto; padding: 1; background: #ffffff; }
#train-output {
    height: 1fr; border: tall #bdc3c7;
    padding: 1; background: #f8f9fa; color: #1a1a1a;
}
.form-row { height: auto; margin-bottom: 1; }
#hint-bar { height: auto; padding: 0 1; background: #ecf0f1; color: #7f8c8d; }
"""


class TrainScreen(Screen):
    """Screen for ML model training."""

    BINDINGS = [
        Binding("escape", "pop_screen", "Back", priority=True),
        Binding("q", "pop_screen", "Back", show=False, priority=True),
        Binding("left", "pop_screen", "Back", show=False),
        Binding("f5", "train", "Train", priority=True),
    ]

    CSS = SCREEN_CSS

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(
            "Tab: next field  Space: toggle checkbox  F5: train  Esc: back",
            id="hint-bar",
        )
        with ScrollableContainer():
            with Vertical(id="train-form"):
                yield Label("Training Data File:")
                yield Input(value="corpus/labelled/sample.csv", id="data-path")
                yield Label("Models to Train:")
                yield Checkbox("Topic Classifier", value=True, id="chk-classifier")
                yield Checkbox("Quality Regressor", value=True, id="chk-regressor")
                yield Checkbox("Hypothetical Clusterer", value=True, id="chk-clusterer")
                with Horizontal(classes="form-row"):
                    yield Label("Clusters:")
                    yield Input(value="5", id="n-clusters")
                with Horizontal(classes="form-row"):
                    yield Label("Test Split:")
                    yield Input(value="0.2", id="test-split")
                with Horizontal(classes="form-row"):
                    yield Label("Max Features:")
                    yield Input(value="5000", id="max-features")
                yield ProgressBar(total=100, show_eta=True, id="train-progress")
            yield Static("Press F5 to start training...", id="train-output")
        yield Footer()

    async def action_train(self) -> None:
        output = self.query_one("#train-output", Static)
        progress = self.query_one("#train-progress", ProgressBar)
        output.update("Training...")
        try:
            from ...ml.pipeline import MLPipeline

            data_path = self.query_one("#data-path", Input).value
            n_clusters = int(self.query_one("#n-clusters", Input).value or "5")
            max_features = int(
                self.query_one("#max-features", Input).value or "5000"
            )
            pipeline = MLPipeline()

            def on_progress(pct, msg):
                self.call_from_thread(progress.update, progress=int(pct * 100))

            import asyncio

            metrics = await asyncio.to_thread(
                pipeline.train_all,
                data_path,
                progress_callback=on_progress,
                n_clusters=n_clusters,
                max_features=max_features,
            )
            output.update(f"Training complete!\n\n{metrics}")
        except Exception as e:
            output.update(f"Error: {e}")
