"""Jikai TUI - Main Textual App."""

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Footer, Header, Static


class Sidebar(Static):
    """Navigation sidebar."""

    def compose(self) -> ComposeResult:
        yield Static(
            "[b]Navigation[/b]\n\n"
            "[g] Generate\n"
            "[t] Train ML\n"
            "[b] Browse Corpus\n"
            "[s] Settings\n"
            "[p] Providers\n"
            "[q] Quit",
            id="nav-content",
        )

    DEFAULT_CSS = """
    Sidebar {
        width: 24;
        dock: left;
        background: $surface;
        border-right: tall $primary;
        padding: 1;
    }
    """


class ContentArea(Static):
    """Main content area placeholder."""

    DEFAULT_CSS = """
    ContentArea {
        width: 1fr;
        height: 1fr;
        padding: 1;
    }
    """


class JikaiApp(App):
    """Jikai TUI Application."""

    TITLE = "Jikai - Legal Hypothetical Generator"
    CSS = """
    Screen {
        background: $surface-darken-1;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("g", "show_generate", "Generate"),
        Binding("t", "show_train", "Train ML"),
        Binding("b", "show_corpus", "Browse Corpus"),
        Binding("s", "show_settings", "Settings"),
        Binding("p", "show_providers", "Providers"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            yield Sidebar()
            yield ContentArea(
                "Welcome to Jikai. Use keybindings to navigate.", id="content"
            )
        yield Footer()

    def action_show_generate(self) -> None:
        from .screens.generate import GenerateScreen

        self.push_screen(GenerateScreen())

    def action_show_train(self) -> None:
        from .screens.train import TrainScreen

        self.push_screen(TrainScreen())

    def action_show_corpus(self) -> None:
        from .screens.corpus import CorpusScreen

        self.push_screen(CorpusScreen())

    def action_show_settings(self) -> None:
        from .screens.settings import SettingsScreen

        self.push_screen(SettingsScreen())

    def action_show_providers(self) -> None:
        from .screens.providers import ProvidersScreen

        self.push_screen(ProvidersScreen())
