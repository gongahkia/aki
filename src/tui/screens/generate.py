"""Generate screen for hypothetical generation."""
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Footer, Static, Button, Select, Input, RadioSet, RadioButton, Label, TextArea
from textual.containers import Vertical, Horizontal, ScrollableContainer
from textual.binding import Binding


class GenerateScreen(Screen):
    """Screen for generating legal hypotheticals."""

    BINDINGS = [Binding("escape", "pop_screen", "Back")]

    CSS = """
    GenerateScreen {
        layout: vertical;
    }
    #generate-form {
        height: auto;
        padding: 1;
    }
    #output-panel {
        height: 1fr;
        border: tall $primary;
        padding: 1;
    }
    .form-row {
        height: auto;
        margin-bottom: 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        with ScrollableContainer():
            with Vertical(id="generate-form"):
                yield Label("Topic Selection")
                yield Select(
                    [(t, t) for t in [
                        "negligence", "duty_of_care", "causation", "remoteness",
                        "battery", "assault", "false_imprisonment", "defamation",
                        "private_nuisance", "trespass_to_land", "vicarious_liability",
                        "strict_liability", "harassment", "occupiers_liability",
                        "product_liability", "contributory_negligence", "economic_loss",
                        "psychiatric_harm", "employers_liability",
                    ]],
                    prompt="Select topic", id="topic-select",
                )
                with Horizontal(classes="form-row"):
                    yield Label("Provider:")
                    yield Select(
                        [("ollama", "ollama"), ("openai", "openai"),
                         ("anthropic", "anthropic"), ("google", "google"), ("local", "local")],
                        prompt="Provider", id="provider-select",
                    )
                with Horizontal(classes="form-row"):
                    yield Label("Model:")
                    yield Input(placeholder="Model name (optional)", id="model-input")
                with Horizontal(classes="form-row"):
                    yield Label("Complexity (1-5):")
                    yield Input(value="3", id="complexity-input")
                with Horizontal(classes="form-row"):
                    yield Label("Parties (2-5):")
                    yield Input(value="3", id="parties-input")
                yield Label("Method:")
                with RadioSet(id="method-radio"):
                    yield RadioButton("Pure LLM", value=True, id="pure_llm")
                    yield RadioButton("ML-Assisted", id="ml_assisted")
                    yield RadioButton("Hybrid", id="hybrid")
                yield Button("Generate", variant="primary", id="generate-btn")
            yield Static("Output will appear here...", id="output-panel")
        yield Footer()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "generate-btn":
            output = self.query_one("#output-panel", Static)
            output.update("[bold yellow]Generating...[/bold yellow]")
            try:
                from ...services.hypothetical_service import hypothetical_service, GenerationRequest
                topic_sel = self.query_one("#topic-select", Select)
                topic = topic_sel.value if topic_sel.value != Select.BLANK else "negligence"
                complexity = int(self.query_one("#complexity-input", Input).value or "3")
                parties = int(self.query_one("#parties-input", Input).value or "3")
                request = GenerationRequest(
                    topics=[topic],
                    number_parties=max(2, min(5, parties)),
                    complexity_level=max(1, min(5, complexity)),
                )
                response = await hypothetical_service.generate_hypothetical(request)
                text = response.hypothetical if hasattr(response, "hypothetical") else str(response)
                output.update(text)
            except Exception as e:
                output.update(f"[bold red]Error: {e}[/bold red]")
