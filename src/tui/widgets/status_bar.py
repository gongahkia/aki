"""Status bar widget for Textual screens."""

from __future__ import annotations

from textual.reactive import reactive
from textual.widgets import Static


def _badge(label: str, state: str) -> str:
    palette = {
        "ok": "green",
        "warn": "yellow",
        "error": "red",
        "unknown": "grey66",
    }
    color = palette.get(state, "grey66")
    return f"[{color}]●[/{color}] {label}"


class StatusBar(Static):
    """Compact health/status badges for core runtime dependencies."""

    corpus_state = reactive("unknown")
    models_state = reactive("unknown")
    embeddings_state = reactive("unknown")
    provider_state = reactive("unknown")

    def set_states(
        self,
        *,
        corpus: str,
        models: str,
        embeddings: str,
        provider: str,
    ) -> None:
        self.corpus_state = corpus
        self.models_state = models
        self.embeddings_state = embeddings
        self.provider_state = provider

    def _render(self) -> str:
        parts = [
            _badge("Corpus", self.corpus_state),
            _badge("Models", self.models_state),
            _badge("Embeddings", self.embeddings_state),
            _badge("Provider", self.provider_state),
        ]
        return "   ".join(parts)

    def on_mount(self) -> None:
        self.update(self._render())

    def watch_corpus_state(self) -> None:
        self.update(self._render())

    def watch_models_state(self) -> None:
        self.update(self._render())

    def watch_embeddings_state(self) -> None:
        self.update(self._render())

    def watch_provider_state(self) -> None:
        self.update(self._render())
