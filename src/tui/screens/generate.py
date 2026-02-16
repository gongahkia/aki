"""Generate screen for hypothetical generation."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.screen import Screen
from textual.widgets import (
    Footer,
    Header,
    Input,
    Label,
    RadioButton,
    RadioSet,
    Select,
    Static,
)

SCREEN_CSS = """
GenerateScreen {
    layout: vertical;
    background: #ffffff;
    color: #1a1a1a;
}
#generate-form {
    height: auto;
    padding: 1;
    background: #ffffff;
}
#output-panel {
    height: 1fr;
    border: tall #bdc3c7;
    padding: 1;
    background: #f8f9fa;
    color: #1a1a1a;
}
.form-row {
    height: auto;
    margin-bottom: 1;
}
#hint-bar {
    height: auto;
    padding: 0 1;
    background: #ecf0f1;
    color: #7f8c8d;
}
"""


class GenerateScreen(Screen):
    """Screen for generating legal hypotheticals."""

    BINDINGS = [
        Binding("escape", "pop_screen", "Back", priority=True),
        Binding("q", "pop_screen", "Back", show=False, priority=True),
        Binding("left", "pop_screen", "Back", show=False),
        Binding("f5", "generate", "Generate", priority=True),
    ]

    CSS = SCREEN_CSS

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(
            "Tab: next field  ↑↓: select options  F5: generate  Esc: back",
            id="hint-bar",
        )
        with ScrollableContainer():
            with Vertical(id="generate-form"):
                yield Label("Topic Selection")
                yield Select(
                    [
                        (t, t)
                        for t in [
                            "negligence",
                            "duty_of_care",
                            "causation",
                            "remoteness",
                            "battery",
                            "assault",
                            "false_imprisonment",
                            "defamation",
                            "private_nuisance",
                            "trespass_to_land",
                            "vicarious_liability",
                            "strict_liability",
                            "harassment",
                            "occupiers_liability",
                            "product_liability",
                            "contributory_negligence",
                            "economic_loss",
                            "psychiatric_harm",
                            "employers_liability",
                        ]
                    ],
                    prompt="Select topic",
                    id="topic-select",
                )
                with Horizontal(classes="form-row"):
                    yield Label("Provider:")
                    yield Select(
                        [
                            ("ollama", "ollama"),
                            ("openai", "openai"),
                            ("anthropic", "anthropic"),
                            ("google", "google"),
                            ("local", "local"),
                        ],
                        prompt="Provider",
                        id="provider-select",
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
            yield Static("Press F5 to generate...", id="output-panel")
        yield Footer()

    async def action_generate(self) -> None:
        output = self.query_one("#output-panel", Static)
        output.update("Generating...")
        try:
            from ...services.hypothetical_service import (
                GenerationRequest,
                hypothetical_service,
            )
            from ...services.llm_service import LLMRequest, llm_service

            topic_sel = self.query_one("#topic-select", Select)
            topic = (
                topic_sel.value if topic_sel.value != Select.BLANK else "negligence"
            )
            complexity = int(
                self.query_one("#complexity-input", Input).value or "3"
            )
            parties = int(self.query_one("#parties-input", Input).value or "3")
            provider_sel = self.query_one("#provider-select", Select)
            provider = (
                provider_sel.value if provider_sel.value != Select.BLANK else None
            )
            model_val = self.query_one("#model-input", Input).value or None
            try:
                request = LLMRequest(
                    prompt=(
                        f"Generate a Singapore tort law hypothetical about {topic}"
                        f" with {parties} parties at complexity {complexity}/5."
                    ),
                    stream=True,
                )
                chunks = []
                async for chunk in llm_service.stream_generate(
                    request, provider=provider, model=model_val
                ):
                    chunks.append(chunk)
                    output.update("".join(chunks))
                if not chunks:
                    output.update("No output received")
            except Exception:
                request = GenerationRequest(
                    topics=[topic],
                    number_parties=max(2, min(5, parties)),
                    complexity_level=max(1, min(5, complexity)),
                )
                response = await hypothetical_service.generate_hypothetical(request)
                text = (
                    response.hypothetical
                    if hasattr(response, "hypothetical")
                    else str(response)
                )
                output.update(text)
        except Exception as e:
            output.update(f"Error: {e}")
