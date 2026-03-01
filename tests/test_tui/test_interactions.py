"""Interaction-level TUI tests for core user flows."""

import sys
from types import SimpleNamespace
from typing import Any

from src.services.hypothetical_service import GenerationResponse
from src.tui import JikaiTUI
from src.tui.models import GenerationConfig
from src.tui.state import LastGenerationConfig, TUIState


def test_generate_flow_quick_uses_saved_defaults(monkeypatch):
    app = JikaiTUI()
    captured: dict[str, Any] = {}

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
    selected: dict[str, Any] = {}

    fake_llm_service = SimpleNamespace(
        select_provider=lambda provider: selected.setdefault("provider", provider)
    )
    monkeypatch.setattr(
        "src.tui.rich_app._select_quit", lambda *args, **kwargs: "openai"
    )
    monkeypatch.setitem(
        sys.modules,
        "src.services.llm_service",
        SimpleNamespace(llm_service=fake_llm_service),
    )

    app._set_default_provider()

    assert selected["provider"] == "openai"


def test_history_browse_flow_invokes_display(monkeypatch):
    app = JikaiTUI()
    displayed: dict[str, Any] = {}
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


def test_persist_stream_generation_stores_cancellation_snapshot(monkeypatch):
    app = JikaiTUI()
    captured: dict[str, Any] = {}

    async def fake_save_generation(**kwargs):
        captured.update(kwargs)
        return 77

    fake_db_service = SimpleNamespace(save_generation=fake_save_generation)
    monkeypatch.setitem(
        sys.modules,
        "src.services.database_service",
        SimpleNamespace(database_service=fake_db_service),
    )

    generation_id = app._persist_stream_generation(
        topic="negligence",
        provider="ollama",
        model="llama3",
        complexity=3,
        parties=2,
        method="pure_llm",
        temperature=0.6,
        red_herrings=False,
        hypothetical="Partial hypothetical text for cancellation snapshot persistence.",
        validation_results={"passed": False, "quality_score": 0.0, "cancelled": True},
        correlation_id="cancel-test-1",
        include_analysis=False,
        partial_snapshot=True,
        cancellation_metadata={"cancelled": True, "reason": "user_interrupt"},
    )

    assert generation_id == 77
    assert (
        captured["request_data"]["user_preferences"]["cancellation_metadata"][
            "cancelled"
        ]
        is True
    )
    assert captured["response_data"]["metadata"]["partial_snapshot"] is True


def test_report_regenerate_persists_lineage_metadata(monkeypatch):
    app = JikaiTUI()
    saved: dict[str, Any] = {}

    async def fake_save_generation_report(**kwargs):
        return 11

    async def fake_regenerate_generation(**kwargs):
        regenerated = GenerationResponse(
            hypothetical="Regenerated hypothetical",
            analysis="Regenerated analysis",
            metadata={"generation_id": 99},
            generation_time=0.4,
            validation_results={"passed": True, "quality_score": 8.2},
        )
        return SimpleNamespace(
            regenerated=regenerated,
            request_data={
                "topics": ["negligence"],
                "provider": "ollama",
                "model": "llama3",
                "complexity_level": 3,
                "number_parties": 2,
                "method": "pure_llm",
            },
        )

    monkeypatch.setattr(
        "src.tui.rich_app._checkbox", lambda *args, **kwargs: ["topic_mismatch"]
    )
    monkeypatch.setattr(
        "src.tui.rich_app._text", lambda *args, **kwargs: "Needs better issue spread"
    )
    monkeypatch.setattr("src.tui.rich_app._confirm", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        "src.tui.rich_app.workflow_facade",
        SimpleNamespace(
            save_generation_report=fake_save_generation_report,
            regenerate_generation=fake_regenerate_generation,
            list_generation_reports=lambda generation_id: [],
        ),
    )
    monkeypatch.setattr(app, "_show_validation", lambda *_: None)
    monkeypatch.setattr(
        app, "_save_to_history", lambda payload: saved.setdefault("payload", payload)
    )

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

    assert result is not None
    lineage = saved["payload"]
    assert lineage["generation_id"] == 99
    assert lineage["regenerated_from"] == 1
    assert lineage["report_id"] == 11
    assert lineage["report_issue_types"] == ["topic_mismatch"]
