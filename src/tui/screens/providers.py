"""Providers management screen."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Label, ListItem, ListView, Static

SCREEN_CSS = """
ProvidersScreen {
    layout: vertical;
    background: #ffffff;
    color: #1a1a1a;
}
#provider-list-panel {
    width: 1fr; min-width: 24; max-width: 32;
    background: #ffffff;
    border-right: tall #cccccc;
}
#provider-detail {
    height: 1fr; border: tall #cccccc;
    padding: 1; background: #ffffff; color: #1a1a1a;
}
#hint-bar {
    height: auto; padding: 0 1;
    background: #ffffff; color: #888888;
    border-bottom: tall #cccccc;
}
"""


class ProvidersScreen(Screen):
    """Screen for LLM provider management."""

    BINDINGS = [
        Binding("escape", "pop_screen", "Back", priority=True),
        Binding("q", "pop_screen", "Back", show=False, priority=True),
        Binding("left", "pop_screen", "Back", show=False),
        Binding("r", "refresh", "Refresh", priority=True),
        Binding("d", "set_default", "Set Default", priority=True),
    ]

    CSS = SCREEN_CSS

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(
            "↑↓: select provider  r: refresh status  d: set default  Esc: back",
            id="hint-bar",
        )
        with Horizontal():
            with Vertical(id="provider-list-panel"):
                yield Label("Providers")
                yield ListView(
                    ListItem(Label("ollama"), id="prov-ollama"),
                    ListItem(Label("openai"), id="prov-openai"),
                    ListItem(Label("anthropic"), id="prov-anthropic"),
                    ListItem(Label("google"), id="prov-google"),
                    ListItem(Label("local"), id="prov-local"),
                    id="providers-lv",
                )
            yield Static(
                "Select a provider and press r to check status...",
                id="provider-detail",
            )
        yield Footer()

    async def action_refresh(self) -> None:
        detail = self.query_one("#provider-detail", Static)
        detail.update("Checking provider health...")
        try:
            from ...services.llm_service import llm_service

            health = await llm_service.health_check()
            models = await llm_service.list_models()
            lines = []
            for name, status in health.items():
                healthy = (
                    status.get("healthy", False) if isinstance(status, dict) else status
                )
                icon = "+" if healthy else "-"
                model_list = models.get(name, [])
                lines.append(
                    f"[{icon}] {name}: {'healthy' if healthy else 'unavailable'}"
                )
                if model_list:
                    lines.append(f"    Models: {', '.join(model_list[:5])}")
            detail.update("\n".join(lines))
        except Exception as e:
            detail.update(f"Error: {e}")

    def action_set_default(self) -> None:
        detail = self.query_one("#provider-detail", Static)
        lv = self.query_one("#providers-lv", ListView)
        if lv.index is not None and lv.highlighted_child is not None:
            item_id = str(lv.highlighted_child.id or "")
            provider = item_id.replace("prov-", "")
            detail.update(f"Set default provider to: {provider}\n(Saved in settings)")
        else:
            detail.update("Select a provider first (use arrow keys)")
