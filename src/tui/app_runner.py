"""Runtime facade for selecting and bootstrapping Jikai interfaces."""

from __future__ import annotations

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
        run_tui(ui=ui)
        return
    if mode == "tui-only":
        run_tui(ui=ui)
        return
    if mode == "both":
        run_tui(ui=ui)
        return
    run_tui(ui=ui)
