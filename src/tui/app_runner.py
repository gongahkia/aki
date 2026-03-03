"""Runtime facade -- starts API server for Rust TUI consumption."""

from __future__ import annotations


def run(mode: str = "api", **_kw) -> None:
    import uvicorn

    uvicorn.run("src.api.main:app", host="127.0.0.1", port=8000, reload=False)
