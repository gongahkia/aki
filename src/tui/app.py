"""Jikai TUI - Main Textual App."""

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header, Label, ListItem, ListView, Static

NAV_ITEMS = [
    ("generate", "Generate", "g"),
    ("train", "Train ML", "t"),
    ("corpus", "Browse Corpus", "b"),
    ("settings", "Settings", "s"),
    ("providers", "Providers", "p"),
]

LIGHT_THEME = """
Screen {
    background: #ffffff;
    color: #1a1a1a;
}
Header {
    background: #2c3e50;
    color: #ffffff;
}
Footer {
    background: #ecf0f1;
    color: #2c3e50;
}
FooterKey {
    background: #2c3e50;
    color: #ffffff;
}
Sidebar {
    background: #f8f9fa;
    border-right: tall #bdc3c7;
    color: #1a1a1a;
}
ListView {
    background: #f8f9fa;
    color: #1a1a1a;
}
ListView > ListItem {
    background: #f8f9fa;
    color: #1a1a1a;
}
ListView > ListItem.--highlight {
    background: #3498db;
    color: #ffffff;
}
ContentArea {
    background: #ffffff;
    color: #1a1a1a;
}
Input {
    background: #f8f9fa;
    color: #1a1a1a;
    border: tall #bdc3c7;
}
Input:focus {
    border: tall #3498db;
}
Select {
    background: #f8f9fa;
    color: #1a1a1a;
}
DataTable {
    background: #ffffff;
    color: #1a1a1a;
}
DataTable > .datatable--header {
    background: #ecf0f1;
    color: #2c3e50;
}
DataTable > .datatable--cursor {
    background: #3498db;
    color: #ffffff;
}
DirectoryTree {
    background: #f8f9fa;
    color: #1a1a1a;
}
ProgressBar {
    background: #ecf0f1;
}
Checkbox {
    background: transparent;
    color: #1a1a1a;
}
RadioButton {
    background: transparent;
    color: #1a1a1a;
}
Static {
    background: transparent;
    color: #1a1a1a;
}
Label {
    color: #1a1a1a;
}
ScrollableContainer {
    background: #ffffff;
}
Vertical {
    background: transparent;
}
Horizontal {
    background: transparent;
}
#nav-hint {
    color: #7f8c8d;
    margin-top: 1;
}
"""


class Sidebar(Vertical):
    """Navigation sidebar with arrow key support."""

    DEFAULT_CSS = """
    Sidebar {
        width: 26;
        dock: left;
        padding: 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield Label("[b]Navigation[/b]")
        yield ListView(
            *[
                ListItem(Label(f"[{key}] {label}"), id=f"nav-{name}")
                for name, label, key in NAV_ITEMS
            ],
            id="nav-list",
        )
        yield Static("↑↓ move  Enter select  q quit", id="nav-hint")


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
    CSS = LIGHT_THEME

    BINDINGS = [
        Binding("q", "quit", "Quit", priority=True),
        Binding("g", "show_generate", "Generate", priority=True),
        Binding("t", "show_train", "Train ML", priority=True),
        Binding("b", "show_corpus", "Browse Corpus", priority=True),
        Binding("s", "show_settings", "Settings", priority=True),
        Binding("p", "show_providers", "Providers", priority=True),
        Binding("enter", "activate_selected", "Select", show=False),
    ]

    _NAV_ACTIONS = {
        "nav-generate": "show_generate",
        "nav-train": "show_train",
        "nav-corpus": "show_corpus",
        "nav-settings": "show_settings",
        "nav-providers": "show_providers",
    }

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            yield Sidebar()
            yield ContentArea(
                "Welcome to Jikai.\n\n"
                "Use ↑↓ arrows to navigate the sidebar, Enter to select.\n"
                "Or press g/t/b/s/p to jump directly.\n"
                "Press q to quit.",
                id="content",
            )
        yield Footer()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle Enter on a nav list item."""
        action = self._NAV_ACTIONS.get(str(event.item.id))
        if action:
            getattr(self, f"action_{action}")()

    def action_activate_selected(self) -> None:
        """Forward Enter to the nav list if focused."""
        try:
            lv = self.query_one("#nav-list", ListView)
            if lv.index is not None and lv.has_focus:
                lv.action_select_cursor()
        except Exception:
            pass

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
