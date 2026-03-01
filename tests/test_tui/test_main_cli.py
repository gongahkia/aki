"""CLI behavior tests for TUI runtime selection."""

import sys
from types import SimpleNamespace

from src.tui import __main__ as cli


def test_tui_only_rich_uses_rich_runtime(monkeypatch):
    calls = []

    monkeypatch.setattr(cli, "run_api", lambda: calls.append(("api", None)))
    monkeypatch.setattr(cli, "run_tui", lambda ui="textual": calls.append(("tui", ui)))
    monkeypatch.setattr(sys, "argv", ["jikai", "--tui-only", "--ui", "rich"])

    cli.main()

    assert calls == [("tui", "rich")]


def test_api_only_rich_does_not_start_tui(monkeypatch):
    calls = []

    monkeypatch.setattr(cli, "run_api", lambda: calls.append(("api", None)))
    monkeypatch.setattr(cli, "run_tui", lambda ui="textual": calls.append(("tui", ui)))
    monkeypatch.setattr(sys, "argv", ["jikai", "--api-only", "--ui", "rich"])

    cli.main()

    assert calls == [("api", None)]


def test_both_rich_starts_api_thread_and_rich_tui(monkeypatch):
    calls = []

    class FakeThread:
        def __init__(self, target, daemon=False):
            self._target = target
            self._daemon = daemon

        def start(self):
            calls.append(("thread_start", self._daemon))
            self._target()

    monkeypatch.setattr(cli, "run_api", lambda: calls.append(("api", None)))
    monkeypatch.setattr(cli, "run_tui", lambda ui="textual": calls.append(("tui", ui)))
    monkeypatch.setattr(cli, "threading", SimpleNamespace(Thread=FakeThread))
    monkeypatch.setattr(sys, "argv", ["jikai", "--both", "--ui", "rich"])

    cli.main()

    assert calls == [("thread_start", True), ("api", None), ("tui", "rich")]
