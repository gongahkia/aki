"""Unit tests for TUI history record validators."""

from src.tui.history_models import validate_history_records


def test_validate_history_records_normalizes_legacy_score():
    records, dropped = validate_history_records(
        [
            {
                "timestamp": "2026-01-01T00:00:00",
                "config": {"topic": "negligence", "parties": 3, "method": "pure_llm"},
                "hypothetical": "Example hypothetical",
                "score": 7.5,
            }
        ]
    )

    assert dropped == 0
    assert len(records) == 1
    assert records[0]["validation_score"] == 7.5


def test_validate_history_records_drops_invalid_payload():
    records, dropped = validate_history_records(
        [
            {
                "timestamp": "2026-01-01T00:00:00",
                "config": {
                    "topic": "negligence",
                    "parties": 8,
                    "method": "pure_llm",
                },
                "hypothetical": "Invalid because parties exceeds bounds",
                "validation_score": 6.0,
            }
        ]
    )

    assert records == []
    assert dropped == 1
