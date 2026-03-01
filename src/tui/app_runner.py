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
    """Run the selected TUI surface."""
    run_tui(ui=ui)
