"""Structured TUI event logging."""

from __future__ import annotations

import structlog

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ]
)

_logger = structlog.get_logger("jikai.tui.events")


def log_tui_event(event: str, **payload) -> None:
    """Emit a structured TUI event."""
    _logger.info(event, **payload)
