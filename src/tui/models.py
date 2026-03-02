"""Shared TUI data models."""

from dataclasses import dataclass, field
from typing import List, Optional

from .state import LastGenerationConfig


@dataclass
class GenerationConfig:
    """Encapsulates all generation parameters."""

    topics: List[str]
    provider: str
    model: Optional[str]
    complexity: int
    parties: int
    method: str
    temperature: float = 0.7
    red_herrings: bool = False
    include_analysis: bool = True

    @classmethod
    def from_inputs(
        cls,
        *,
        topics: List[str],
        provider: str,
        model: Optional[str],
        complexity: str,
        parties: str,
        method: str,
        temperature: str,
        red_herrings: bool,
        include_analysis: bool,
    ) -> "GenerationConfig":
        """Build config from UI string values with strict type coercion."""
        return cls(
            topics=topics,
            provider=provider,
            model=model or None,
            complexity=int(complexity),
            parties=int(parties),
            method=method,
            temperature=float(temperature),
            red_herrings=red_herrings,
            include_analysis=include_analysis,
        )

    def to_last_config(self) -> LastGenerationConfig:
        """Create persisted quick-generate defaults from current config."""
        return LastGenerationConfig(
            provider=self.provider,
            model=self.model,
            temperature=self.temperature,
            complexity=str(self.complexity),
            parties=str(self.parties),
            method=self.method,
            include_analysis=self.include_analysis,
        )
