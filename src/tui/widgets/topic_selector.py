"""Multi-select topic selector widget grouped by tort category."""

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Checkbox, Static

TOPIC_CATEGORIES = {
    "General Negligence": [
        "negligence",
        "duty_of_care",
        "standard_of_care",
        "causation",
        "remoteness",
        "res_ipsa_loquitur",
        "novus_actus_interveniens",
        "contributory_negligence",
        "economic_loss",
        "psychiatric_harm",
    ],
    "Intentional Torts": [
        "battery",
        "assault",
        "false_imprisonment",
        "defamation",
        "harassment",
    ],
    "Land Torts": [
        "private_nuisance",
        "trespass_to_land",
        "occupiers_liability",
        "rylands_v_fletcher",
    ],
    "Strict Liability": [
        "strict_liability",
        "vicarious_liability",
        "employers_liability",
        "product_liability",
        "breach_of_statutory_duty",
    ],
    "Defences": [
        "consent_defence",
        "illegality_defence",
        "limitation_periods",
        "volenti_non_fit_injuria",
    ],
}


class TopicSelector(Vertical):
    """Multi-select checkbox tree grouped by tort category."""

    DEFAULT_CSS = """
    TopicSelector { height: auto; padding: 1; }
    .category-header { text-style: bold; margin-top: 1; }
    """

    def __init__(self):
        super().__init__()
        self._selected: set = set()

    def compose(self) -> ComposeResult:
        yield Static("[bold]Topics[/bold] (0 selected)", id="topic-count")
        for category, topics in TOPIC_CATEGORIES.items():
            yield Static(f"[bold]{category}[/bold]", classes="category-header")
            for topic in topics:
                yield Checkbox(topic.replace("_", " ").title(), id=f"topic-{topic}")

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        topic_id = event.checkbox.id
        if topic_id and topic_id.startswith("topic-"):
            topic = topic_id[6:]
            if event.value:
                self._selected.add(topic)
            else:
                self._selected.discard(topic)
            count_label = self.query_one("#topic-count", Static)
            count_label.update(f"[bold]Topics[/bold] ({len(self._selected)} selected)")

    @property
    def selected_topics(self) -> list:
        return sorted(self._selected)

    def select_category(self, category: str):
        """Select all topics in a category."""
        topics = TOPIC_CATEGORIES.get(category, [])
        for topic in topics:
            cb = self.query_one(f"#topic-{topic}", Checkbox)
            cb.value = True

    def clear_all(self):
        """Clear all selections."""
        for cb in self.query(Checkbox):
            cb.value = False
        self._selected.clear()
