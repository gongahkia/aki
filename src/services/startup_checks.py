"""Startup validation helpers for required runtime assets."""

import json
from pathlib import Path
from typing import Union


class StartupCheckError(RuntimeError):
    """Raised when startup prerequisites are not met."""


def ensure_required_tort_corpus_file(path: Union[str, Path]) -> Path:
    """Validate that the required tort corpus file exists and is usable."""
    corpus_path = Path(path).expanduser()
    if not corpus_path.exists():
        raise StartupCheckError(
            "Required tort corpus file is missing at "
            f"'{corpus_path}'. Run `make preprocess` to build it."
        )

    if not corpus_path.is_file():
        raise StartupCheckError(
            f"Configured corpus path '{corpus_path}' is not a file."
        )

    if corpus_path.stat().st_size == 0:
        raise StartupCheckError(
            f"Configured corpus file '{corpus_path}' is empty. "
            "Run `make preprocess` to regenerate it."
        )

    try:
        payload = json.loads(corpus_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise StartupCheckError(
            f"Configured corpus file '{corpus_path}' is not valid JSON."
        ) from exc

    if not isinstance(payload, list) or not payload:
        raise StartupCheckError(
            f"Configured corpus file '{corpus_path}' has no entries. "
            "Run `make preprocess` to rebuild it."
        )

    return corpus_path
