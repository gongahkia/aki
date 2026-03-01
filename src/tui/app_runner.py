"""Runtime facade for selecting and bootstrapping Jikai interfaces."""

from __future__ import annotations

import threading


def run_api() -> None:
    """Run FastAPI server."""
    import uvicorn

    uvicorn.run("src.api.main:app", host="127.0.0.1", port=8000, reload=False)


def run_tui(ui: str = "textual") -> None:
    """Run selected TUI runtime."""
    if ui == "rich":
        from src.tui.legacy.rich_app import JikaiTUI

        JikaiTUI().run()
        return

    from src.tui.textual_app import JikaiTextualApp

    JikaiTextualApp().run()


def run(mode: str, *, ui: str = "textual") -> None:
    """Run api-only, tui-only, or both surfaces."""
    if mode == "api-only":
        run_api()
        return
    if mode == "tui-only":
        run_tui(ui=ui)
        return
    if mode == "both":
        api_thread = threading.Thread(target=run_api, daemon=True)
        api_thread.start()
        run_tui(ui=ui)
        return
    run_tui(ui=ui)
