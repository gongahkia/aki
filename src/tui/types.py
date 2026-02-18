"""Jikai TUI Data Types."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class GenerationConfig:
    """Encapsulates all generation parameters."""

    topic: str
    provider: str
    model: Optional[str]
    complexity: int
    parties: int
    method: str
    temperature: float = 0.7
    red_herrings: bool = False
