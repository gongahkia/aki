"""Typed state models for TUI persistence."""

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional


@dataclass
class LastGenerationConfig:
    provider: str = "ollama"
    model: Optional[str] = None
    temperature: float = 0.7
    complexity: str = "3"
    parties: str = "2"
    method: str = "pure_llm"
    include_analysis: bool = True


@dataclass
class TUIState:
    last_config: LastGenerationConfig = field(default_factory=LastGenerationConfig)

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "TUIState":
        data = payload if isinstance(payload, dict) else {}
        raw_last_config = data.get("last_config", {})
        if not isinstance(raw_last_config, dict):
            raw_last_config = {}

        raw_temperature = raw_last_config.get("temperature", 0.7)
        try:
            temperature = float(raw_temperature)
        except (TypeError, ValueError):
            temperature = 0.7

        raw_include_analysis = raw_last_config.get("include_analysis", True)
        if isinstance(raw_include_analysis, str):
            include_analysis = raw_include_analysis.strip().lower() not in {
                "",
                "0",
                "false",
                "no",
                "off",
            }
        else:
            include_analysis = bool(raw_include_analysis)

        return cls(
            last_config=LastGenerationConfig(
                provider=str(raw_last_config.get("provider", "ollama")),
                model=(
                    str(raw_last_config.get("model"))
                    if raw_last_config.get("model") not in (None, "")
                    else None
                ),
                temperature=temperature,
                complexity=str(raw_last_config.get("complexity", "3")),
                parties=str(raw_last_config.get("parties", "2")),
                method=str(raw_last_config.get("method", "pure_llm")),
                include_analysis=include_analysis,
            )
        )

    def to_dict(self) -> Dict[str, Any]:
        return {"last_config": asdict(self.last_config)}
