"""Binding regression tests for the Textual app."""

from src.tui.textual_app import JikaiTextualApp


def test_global_bindings_include_primary_shortcuts():
    keys = {binding.key for binding in JikaiTextualApp.BINDINGS}

    assert "q" in keys
    assert "question_mark" in keys
    assert "g" in keys
    assert "h" in keys
    assert "p" in keys
