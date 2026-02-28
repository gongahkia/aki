"""Interaction-level TUI tests for core user flows."""

import sys
from types import SimpleNamespace

from src.tui.rich_app import GenerationConfig, JikaiTUI
from src.tui.state import LastGenerationConfig, TUIState


def test_generate_flow_quick_uses_saved_defaults(monkeypatch):
    app = JikaiTUI()
    captured = {}

    select_values = iter(["quick", "negligence"])
    confirm_values = iter([True, True, False])

    monkeypatch.setattr(
        "src.tui.rich_app._select_quit",
        lambda *args, **kwargs: next(select_values),
    )
    monkeypatch.setattr(
        "src.tui.rich_app._confirm",
        lambda *args, **kwargs: next(confirm_values),
    )
    monkeypatch.setattr(
        app,
        "_load_state",
        lambda: TUIState(
            last_config=LastGenerationConfig(
                provider="ollama",
                model="llama3",
                temperature=0.6,
                complexity="3",
                parties="2",
                method="pure_llm",
                include_analysis=False,
            )
        ),
    )
    monkeypatch.setattr(app, "_save_state", lambda state: None)
    monkeypatch.setattr(
        app,
        "_do_generate",
        lambda cfg: captured.setdefault("cfg", cfg),
    )

    app._generate_flow_impl()

    cfg = captured["cfg"]
    assert cfg.topic == "negligence"
    assert cfg.provider == "ollama"
    assert cfg.model == "llama3"
    assert cfg.include_analysis is False


def test_report_regenerate_requires_persisted_generation_id():
    app = JikaiTUI()
    result = app._report_and_regenerate(
        record={"hypothetical": "sample text"},
        cfg=GenerationConfig(
            topic="negligence",
            provider="ollama",
            model="llama3",
            complexity=3,
            parties=2,
            method="pure_llm",
        ),
    )
    assert result is None


def test_report_regenerate_requires_issue_flags(monkeypatch):
    app = JikaiTUI()
    monkeypatch.setattr("src.tui.rich_app._checkbox", lambda *args, **kwargs: [])

    result = app._report_and_regenerate(
        record={"generation_id": 1},
        cfg=GenerationConfig(
            topic="negligence",
            provider="ollama",
            model="llama3",
            complexity=3,
            parties=2,
            method="pure_llm",
        ),
    )
    assert result is None


def test_set_default_provider_flow(monkeypatch):
    app = JikaiTUI()
    selected = {}

    fake_llm_service = SimpleNamespace(
        select_provider=lambda provider: selected.setdefault("provider", provider)
    )
    monkeypatch.setattr("src.tui.rich_app._select_quit", lambda *args, **kwargs: "openai")
    monkeypatch.setitem(
        sys.modules,
        "src.services.llm_service",
        SimpleNamespace(llm_service=fake_llm_service),
    )

    app._set_default_provider()

    assert selected["provider"] == "openai"


def test_history_browse_flow_invokes_display(monkeypatch):
    app = JikaiTUI()
    displayed = {}
    history = [
        {
            "timestamp": "2026-01-01T00:00:00",
            "config": {"topic": "negligence"},
            "hypothetical": "text",
            "validation_score": 8.0,
        }
    ]
    selections = iter(["browse", None])

    monkeypatch.setattr(app, "_load_history", lambda: history)
    monkeypatch.setattr(
        "src.tui.rich_app._select_quit",
        lambda *args, **kwargs: next(selections),
    )
    monkeypatch.setattr(
        app,
        "_display_history",
        lambda records: displayed.setdefault("count", len(records)),
    )

    app._history_flow_impl()

    assert displayed["count"] == 1
