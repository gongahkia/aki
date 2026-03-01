"""CLI behavior tests for TUI runtime selection."""

import sys

from src.tui import __main__ as cli


def test_tui_only_rich_uses_rich_runtime(monkeypatch):
    calls = []

    monkeypatch.setattr(cli, "run", lambda mode, ui="textual": calls.append((mode, ui)))
    monkeypatch.setattr(sys, "argv", ["jikai", "--tui-only", "--ui", "rich"])

    cli.main()

    assert calls == [("tui-only", "rich")]


def test_api_only_rich_does_not_start_tui(monkeypatch):
    calls = []

    monkeypatch.setattr(cli, "run", lambda mode, ui="textual": calls.append((mode, ui)))
    monkeypatch.setattr(sys, "argv", ["jikai", "--api-only", "--ui", "rich"])

    cli.main()

    assert calls == [("api-only", "rich")]


def test_both_rich_starts_api_thread_and_rich_tui(monkeypatch):
    calls = []

    monkeypatch.setattr(cli, "run", lambda mode, ui="textual": calls.append((mode, ui)))
    monkeypatch.setattr(sys, "argv", ["jikai", "--both", "--ui", "rich"])

    cli.main()

    assert calls == [("both", "rich")]
