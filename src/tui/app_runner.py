"""Runtime facade for selecting and bootstrapping Jikai interfaces."""

from __future__ import annotations

def run_tui(ui: str = "rich") -> None:
    """Run selected TUI runtime."""
    if ui != "rich":
        raise ValueError(f"Unsupported UI runtime '{ui}'. Only 'rich' is supported.")

    from src.tui.legacy.rich_app import JikaiTUI
    JikaiTUI().run()


def run(mode: str, *, ui: str = "rich") -> None:
    """Run the selected TUI surface."""
    run_tui(ui=ui)
