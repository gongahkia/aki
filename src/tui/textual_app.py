"""Textual-based TUI runtime for Jikai."""

from __future__ import annotations

from typing import Dict

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import Footer, Header, Label, Static


class _BaseScreen(Screen):
    """Simple base screen with a title and helper copy."""

    screen_title: str = ""
    screen_help: str = ""

    def compose(self) -> ComposeResult:
        with Container(id="screen-body"):
            yield Label(self.screen_title, id="screen-title")
            yield Static(self.screen_help, id="screen-help")


class HomeScreen(_BaseScreen):
    screen_title = "Home"
    screen_help = "Use global shortcuts to navigate core workflows."


class GenerateScreen(_BaseScreen):
    screen_title = "Generate"
    screen_help = "Generation workflow entry point."


class HistoryScreen(_BaseScreen):
    screen_title = "History"
    screen_help = "Browse generation history."


class ProvidersScreen(_BaseScreen):
    screen_title = "Providers"
    screen_help = "Inspect provider health and defaults."


class HelpScreen(_BaseScreen):
    screen_title = "Help"
    screen_help = (
        "Shortcuts: q quit, ? help, g generate, h history, p providers, home home screen."
    )


class JikaiTextualApp(App[None]):
    """Interactive Textual runtime with primary navigation bindings."""

    CSS = """
    #screen-body {
        padding: 1 2;
    }

    #screen-title {
        text-style: bold;
        color: cyan;
        margin-bottom: 1;
    }

    #screen-help {
        color: $text-muted;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("question_mark", "show_help", "Help"),
        Binding("g", "show_generate", "Generate"),
        Binding("h", "show_history", "History"),
        Binding("p", "show_providers", "Providers"),
        Binding("home", "show_home", "Home"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._screens: Dict[str, Screen] = {
            "home": HomeScreen(),
            "generate": GenerateScreen(),
            "history": HistoryScreen(),
            "providers": ProvidersScreen(),
            "help": HelpScreen(),
        }

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Footer()

    def on_mount(self) -> None:
        self.push_screen(self._screens["home"])

    @on(App.PoppedScreen)
    def _on_popped_screen(self) -> None:
        if not self.screen_stack:
            self.push_screen(self._screens["home"])

    def _switch_to(self, key: str) -> None:
        self.pop_screen()
        self.push_screen(self._screens[key])

    def action_show_home(self) -> None:
        self._switch_to("home")

    def action_show_help(self) -> None:
        self._switch_to("help")

    def action_show_generate(self) -> None:
        self._switch_to("generate")

    def action_show_history(self) -> None:
        self._switch_to("history")

    def action_show_providers(self) -> None:
        self._switch_to("providers")
