"""Textual screen unit tests for navigation and generate interactions."""

from types import SimpleNamespace
from typing import Any

from src.tui.screens.generate import GenerateFormScreen
from src.tui.textual_app import JikaiTextualApp


class _FakeStatic:
    def __init__(self, value=""):
        self.value = value

    def update(self, value):
        self.value = value


class _FakeInput:
    def __init__(self, value=""):
        self.value = value


class _FakeSelect:
    def __init__(self, value=""):
        self.value = value


def test_navigation_bindings_include_core_routes():
    keys = {binding.key for binding in JikaiTextualApp.BINDINGS}
    assert "g" in keys
    assert "h" in keys
    assert "p" in keys
    assert "ctrl+k" in keys


def test_generate_form_validation_flags_invalid_parties(monkeypatch):
    screen = GenerateFormScreen(provider_service=SimpleNamespace(stream_generate=None))

    widgets: dict[str, Any] = {
        "#topics": _FakeInput("negligence, causation"),
        "#parties": _FakeInput("1"),
        "#complexity": _FakeSelect("intermediate"),
        "#topics-error": _FakeStatic(),
        "#parties-error": _FakeStatic(),
        "#complexity-error": _FakeStatic(),
    }

    monkeypatch.setattr(screen, "query_one", lambda selector, *_: widgets[selector])

    assert screen._validate_topics() is True
    assert screen._validate_parties() is False
    assert "between 2 and 5" in widgets["#parties-error"].value


def test_generate_post_action_updates_status(monkeypatch):
    screen = GenerateFormScreen(provider_service=SimpleNamespace(stream_generate=None))

    widgets: dict[str, Any] = {
        "#action-status": _FakeStatic("Action dock: idle"),
    }
    monkeypatch.setattr(screen, "query_one", lambda selector, *_: widgets[selector])

    event = SimpleNamespace(button=SimpleNamespace(id="action-export"))
    screen.on_button_pressed(event)

    assert widgets["#action-status"].value == "Action dock: Export selected"
