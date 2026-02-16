"""Settings screen for app configuration."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import ScrollableContainer, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, Select, Static


class SettingsScreen(Screen):
    """Screen for application settings."""

    BINDINGS = [
        Binding("escape", "pop_screen", "Back", priority=True),
        Binding("q", "pop_screen", "Back", show=False, priority=True),
        Binding("left", "pop_screen", "Back", show=False),
    ]

    CSS = """
    SettingsScreen { layout: vertical; }
    #settings-form { padding: 1; }
    .setting-group { margin-bottom: 1; }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        with ScrollableContainer():
            with Vertical(id="settings-form"):
                yield Label("[bold]API Keys[/bold]")
                yield Label("Anthropic API Key:")
                yield Input(placeholder="sk-ant-...", password=True, id="anthropic-key")
                yield Label("OpenAI API Key:")
                yield Input(placeholder="sk-...", password=True, id="openai-key")
                yield Label("Google API Key:")
                yield Input(placeholder="AI...", password=True, id="google-key")
                yield Label("[bold]Hosts[/bold]")
                yield Label("Ollama Host:")
                yield Input(value="http://localhost:11434", id="ollama-host")
                yield Label("Local LLM Host:")
                yield Input(value="http://localhost:8080", id="local-host")
                yield Label("[bold]Defaults[/bold]")
                yield Label("Default Temperature (0.0-2.0):")
                yield Input(value="0.7", id="temperature")
                yield Label("Default Max Tokens:")
                yield Input(value="2048", id="max-tokens")
                yield Label("Corpus Path:")
                yield Input(value="corpus/clean/tort/corpus.json", id="corpus-path")
                yield Label("Database Path:")
                yield Input(value="data/jikai.db", id="db-path")
                yield Label("Log Level:")
                yield Select(
                    [
                        ("DEBUG", "DEBUG"),
                        ("INFO", "INFO"),
                        ("WARNING", "WARNING"),
                        ("ERROR", "ERROR"),
                    ],
                    value="INFO",
                    id="log-level",
                )
                yield Button("Save Settings", variant="primary", id="save-btn")
                yield Static("", id="save-status")
        yield Footer()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save-btn":
            status = self.query_one("#save-status", Static)
            try:
                lines = []
                lines.append(
                    f"ANTHROPIC_API_KEY={self.query_one('#anthropic-key', Input).value}"
                )
                lines.append(
                    f"OPENAI_API_KEY={self.query_one('#openai-key', Input).value}"
                )
                lines.append(
                    f"GOOGLE_API_KEY={self.query_one('#google-key', Input).value}"
                )
                lines.append(
                    f"OLLAMA_HOST={self.query_one('#ollama-host', Input).value}"
                )
                lines.append(
                    f"LOCAL_LLM_HOST={self.query_one('#local-host', Input).value}"
                )
                lines.append(
                    f"DEFAULT_TEMPERATURE={self.query_one('#temperature', Input).value}"
                )
                lines.append(
                    f"DEFAULT_MAX_TOKENS={self.query_one('#max-tokens', Input).value}"
                )
                lines.append(
                    f"CORPUS_PATH={self.query_one('#corpus-path', Input).value}"
                )
                lines.append(f"DATABASE_PATH={self.query_one('#db-path', Input).value}")
                log_sel = self.query_one("#log-level", Select)
                lines.append(f"LOG_LEVEL={log_sel.value}")
                with open(".env", "w") as f:
                    f.write("\n".join(lines) + "\n")
                status.update("[bold green]Settings saved to .env[/bold green]")
            except Exception as e:
                status.update(f"[bold red]Error: {e}[/bold red]")
