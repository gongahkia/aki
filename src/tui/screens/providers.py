"""Providers management screen."""
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Footer, Static, Button, Label, ListView, ListItem
from textual.containers import Vertical, Horizontal, ScrollableContainer
from textual.binding import Binding


class ProvidersScreen(Screen):
    """Screen for LLM provider management."""

    BINDINGS = [Binding("escape", "pop_screen", "Back")]

    CSS = """
    ProvidersScreen { layout: vertical; }
    #provider-list { height: 1fr; }
    #provider-detail { height: 1fr; border: tall $primary; padding: 1; }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            with Vertical(id="provider-list"):
                yield Label("[bold]Providers[/bold]")
                yield ListView(
                    ListItem(Label("ollama"), id="prov-ollama"),
                    ListItem(Label("openai"), id="prov-openai"),
                    ListItem(Label("anthropic"), id="prov-anthropic"),
                    ListItem(Label("google"), id="prov-google"),
                    ListItem(Label("local"), id="prov-local"),
                    id="providers-lv",
                )
                yield Button("Refresh Status", variant="primary", id="refresh-btn")
                yield Button("Set as Default", variant="default", id="set-default-btn")
            yield Static("Select a provider to see details...", id="provider-detail")
        yield Footer()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        detail = self.query_one("#provider-detail", Static)
        if event.button.id == "refresh-btn":
            detail.update("[yellow]Checking provider health...[/yellow]")
            try:
                from ...services.llm_service import llm_service
                health = await llm_service.health_check()
                models = await llm_service.list_models()
                lines = []
                for name, status in health.items():
                    healthy = status.get("healthy", False) if isinstance(status, dict) else status
                    icon = "🟢" if healthy else "🔴"
                    model_list = models.get(name, [])
                    lines.append(f"{icon} [bold]{name}[/bold]: {'healthy' if healthy else 'unavailable'}")
                    if model_list:
                        lines.append(f"   Models: {', '.join(model_list[:5])}")
                detail.update("\n".join(lines))
            except Exception as e:
                detail.update(f"[bold red]Error: {e}[/bold red]")
        elif event.button.id == "set-default-btn":
            detail.update("[yellow]Use keybinding or settings to set default provider.[/yellow]")
