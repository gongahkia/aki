"""Structured TUI event logging."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

import structlog

from ..config.settings import settings

DEFAULT_LOG_FILE = "logs/tui-events.log"
MAX_LOG_BYTES = 5 * 1024 * 1024
BACKUP_LOG_FILES = 5
_LOGGER_NAME = "jikai.tui.events"


def _resolve_log_path() -> Path:
    configured_path = settings.logging.file_path
    if configured_path:
        return Path(configured_path).expanduser()
    project_root = Path(__file__).resolve().parents[2]
    return project_root / DEFAULT_LOG_FILE


def _configure_rotating_handler() -> logging.Logger:
    logger = logging.getLogger(_LOGGER_NAME)
    if logger.handlers:
        return logger

    log_path = _resolve_log_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        log_path,
        maxBytes=MAX_LOG_BYTES,
        backupCount=BACKUP_LOG_FILES,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.setLevel(getattr(logging, settings.logging.level, logging.INFO))
    logger.propagate = False
    return logger


_configure_rotating_handler()
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)
_logger = structlog.get_logger(_LOGGER_NAME)


def log_tui_event(event: str, **payload: Any) -> None:
    """Emit a structured TUI event."""
    _logger.info(event, **payload)
