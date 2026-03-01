"""Runtime facade for selecting and bootstrapping Jikai interfaces."""

from __future__ import annotations


def run_tui(ui: str = "rich") -> None:
    """Run selected TUI runtime."""
    from src.services.database_service import database_service
    from src.services.workflow_facade import workflow_facade

    setattr(workflow_facade, "_database_service", database_service)

    if ui == "rich":
        from src.tui.legacy.rich_app import JikaiTUI

        JikaiTUI().run()
        return

    if ui == "textual":
        from src.tui.textual_app import JikaiTextualApp

        JikaiTextualApp().run()
        return

    raise ValueError(
        f"Unsupported UI runtime '{ui}'. Only 'rich' and 'textual' are supported."
    )


def run(mode: str, *, ui: str = "rich") -> None:
    """Run the selected TUI surface."""
    if mode == "api-only":
        return
    if mode in {"tui-only", "both"}:
        run_tui(ui=ui)
        return
    raise ValueError(f"Unsupported mode '{mode}'")
