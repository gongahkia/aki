"""Atomic environment file persistence for TUI settings."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Iterable


class EnvStore:
    """Read/write .env files with backup and atomic replacement."""

    def __init__(self, path: str = ".env") -> None:
        self.path = Path(path)

    def load(self) -> Dict[str, str]:
        values: Dict[str, str] = {}
        try:
            for line in self.path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    key, value = line.split("=", 1)
                    values[key.strip()] = value.strip()
        except FileNotFoundError:
            pass
        return values

    def save(self, env: Dict[str, str], managed_keys: Iterable[str]) -> None:
        ordered_lines = []
        managed_set = set(managed_keys)
        for key in managed_keys:
            if key in env:
                ordered_lines.append(f"{key}={env[key]}")
        for key, value in env.items():
            if key not in managed_set:
                ordered_lines.append(f"{key}={value}")

        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = "\n".join(ordered_lines) + "\n"

        if self.path.exists():
            backup_path = self.path.with_suffix(self.path.suffix + ".bak")
            backup_path.write_text(self.path.read_text(encoding="utf-8"), encoding="utf-8")

        temp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        fd = os.open(str(temp_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
        os.replace(temp_path, self.path)
