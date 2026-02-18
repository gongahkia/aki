"""Jikai TUI Input Helpers."""

import questionary
from questionary import Choice
from rich.panel import Panel
from rich import box
from prompt_toolkit.key_binding import KeyBindings, merge_key_bindings

from src.tui.console import console
from src.tui.constants import (
    TOPIC_CATEGORIES,
    TOPIC_DESCRIPTIONS,
    PROVIDER_MODELS,
    HOTKEY_MAP,
    GLOBAL_HOTKEYS,
    HELP_DESCRIPTIONS,
)


COMPLEXITY_CHOICES = [
    Choice("1 — Simple", value="1"),
    Choice("2 — Basic", value="2"),
    Choice("3 — Moderate", value="3"),
    Choice("4 — Complex", value="4"),
    Choice("5 — Advanced", value="5"),
]

PARTIES_CHOICES = [
    Choice("2 parties", value="2"),
    Choice("3 parties", value="3"),
    Choice("4 parties", value="4"),
    Choice("5 parties", value="5"),
]

METHOD_CHOICES = [
    Choice("Pure LLM", value="pure_llm"),
    Choice("ML Assisted", value="ml_assisted"),
    Choice("Hybrid", value="hybrid"),
]

PROVIDER_CHOICES = [
    Choice("Ollama (local)", value="ollama"),
    Choice("OpenAI", value="openai"),
    Choice("Anthropic", value="anthropic"),
    Choice("Google", value="google"),
    Choice("Local LLM", value="local"),
]


def _topic_choices():
    """Build topic choices with descriptions, grouped by category."""
    choices = []
    for category, topics in TOPIC_CATEGORIES.items():
        # Add category separator
        choices.append(Choice(f"── {category} ──", value=None, disabled=""))
        for t in topics:
            desc = TOPIC_DESCRIPTIONS.get(t, "")
            title = t.replace("_", " ").title()
            label = f"{title} — {desc}" if desc else title
            choices.append(Choice(label, value=t))
    return choices


def _model_choices(provider):
    choices = [Choice(m, value=m) for m in PROVIDER_MODELS.get(provider, [])]
    choices.append(Choice("Custom...", value="__custom__"))
    return choices


def _select(message, choices):
    """Arrow-key select menu. Returns value or None on Ctrl+C."""
    try:
        return questionary.select(message, choices=choices).ask()
    except KeyboardInterrupt:
        return None


def _show_help_overlay(choices):
    """Show a help panel describing each visible option with contextual descriptions."""
    lines = []
    for c in choices:
        if hasattr(c, "title") and hasattr(c, "value"):
            title = c.title
            if isinstance(title, list):  # prompt_toolkit formatted text tuples
                title = "".join(t[1] for t in title)
            value = c.value
            desc = HELP_DESCRIPTIONS.get(value, "")
            disabled = getattr(c, "disabled", None)
            status = f" [dim]({disabled})[/dim]" if disabled else ""
            if desc:
                lines.append(f"  [cyan]{title}[/cyan]{status}\n    [dim]{desc}[/dim]")
            else:
                lines.append(f"  [cyan]{title}[/cyan]{status}")
    help_text = "\n".join(lines) if lines else "No options available."
    # Add getting started section for first-time users
    getting_started = (
        "[bold]Getting Started:[/bold]\n"
        "  [dim]New here? Start with Import & Preprocess Corpus, then Generate Hypothetical.[/dim]"
    )
    console.print(
        Panel(
            f"[bold]Available Options:[/bold]\n{help_text}\n\n"
            f"{getting_started}\n\n"
            "[dim]Shortcuts: q=quit, g=generate, h=history, s=settings, p=providers[/dim]\n"
            "[dim]Press ? for this help. Press any key to dismiss.[/dim]",
            title="Help",
            box=box.ROUNDED,
            border_style="yellow",
        )
    )


def _select_quit(message, choices, hotkeys=None, style=None, enable_global_hotkeys=True):
    """Arrow-key select with q-to-quit, ?-for-help, and optional hotkey bindings."""
    hk = hotkeys or HOTKEY_MAP
    _result = {"value": None}
    kb = KeyBindings()

    @kb.add("q")
    def _quit_on_q(event):
        event.app.exit(exception=KeyboardInterrupt())

    @kb.add("?")
    def _help_on_question(event):
        _result["value"] = "__help__"
        event.app.exit(result="__help__")

    # Build hotkeys that return corresponding menu values
    choice_values = {c.value for c in choices if hasattr(c, "value")}
    for key, val in hk.items():
        if val in choice_values:

            def _make_handler(v):
                def _handler(event):
                    _result["value"] = v
                    event.app.exit(result=v)

                return _handler

            kb.add(key)(_make_handler(val))

    # Add global hotkeys that work from any submenu (e.g., 'g' to jump to Generate)
    if enable_global_hotkeys:
        for key, val in GLOBAL_HOTKEYS.items():
            if key not in [k for k, v in hk.items() if v in choice_values]:
                def _make_global_handler(v):
                    def _handler(event):
                        _result["value"] = v
                        event.app.exit(result=v)
                    return _handler
                kb.add(key)(_make_global_handler(val))

    hint_keys = " ".join(f"{k}={v}" for k, v in hk.items() if v in choice_values)
    global_hint = "g=generate" if enable_global_hotkeys and "gen" not in choice_values else ""
    all_hints = " | ".join(filter(None, [hint_keys, global_hint]))
    instruction = (
        f"(q quit | ? help | {all_hints})" if all_hints else "(q quit | ? help)"
    )
    while True:
        try:
            _result["value"] = None
            q = questionary.select(
                message, choices=choices, instruction=instruction, style=style
            )
            orig = q.application.key_bindings
            q.application.key_bindings = merge_key_bindings([orig, kb]) if orig else kb
            result = q.unsafe_ask()
            chosen = _result["value"] if _result["value"] is not None else result
            if chosen == "__help__":
                _show_help_overlay(choices)
                continue
            return chosen
        except (KeyboardInterrupt, EOFError):
            return None


def _checkbox(message, choices):
    """Arrow-key checkbox menu. Returns list or None on Ctrl+C."""
    try:
        return questionary.checkbox(message, choices=choices).ask()
    except KeyboardInterrupt:
        return None


def _text(message, default=""):
    """questionary text input with default."""
    try:
        return questionary.text(message, default=default).ask()
    except KeyboardInterrupt:
        return None


def _password(message, default=""):
    """questionary password input (masked)."""
    try:
        return questionary.password(message, default=default).ask()
    except KeyboardInterrupt:
        return None


def _confirm(message, default=True):
    """questionary yes/no confirm."""
    try:
        return questionary.confirm(message, default=default).ask()
    except KeyboardInterrupt:
        return False


def _path(message, default=""):
    """questionary path input with autocomplete."""
    try:
        return questionary.path(message, default=default).ask()
    except KeyboardInterrupt:
        return None


def _validate_number(min_val, max_val, is_float=False):
    """Return a questionary validator for numeric range."""

    def _validator(val):
        try:
            n = float(val) if is_float else int(val)
        except (ValueError, TypeError):
            kind = "float" if is_float else "integer"
            return f"Must be a valid {kind}"
        if n < min_val or n > max_val:
            return f"Must be between {min_val} and {max_val}"
        return True

    return _validator


def _validated_text(message, default="", validate=None):
    """questionary text with validation."""
    try:
        return questionary.text(message, default=default, validate=validate).ask()
    except KeyboardInterrupt:
        return None
