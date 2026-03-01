"""Typed route registry for TUI navigation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass(frozen=True)
class Route:
    """Represents a named TUI route."""

    key: str
    label: str
    description: str


ROUTES: Tuple[Route, ...] = (
    Route("home", "Home", "Top-level navigation and overview."),
    Route("generate", "Generate", "Hypothetical generation workflow."),
    Route("history", "History", "Browse and inspect generation history."),
    Route("providers", "Providers", "Provider status and model selection."),
    Route("training", "Training", "Model training and embedding operations."),
    Route("settings", "Settings", "Runtime and environment configuration."),
)

ROUTE_MAP: Dict[str, Route] = {route.key: route for route in ROUTES}

