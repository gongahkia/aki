"""CLI entry point for Jikai TUI/API."""

import argparse
import threading


def run_api():
    """Run FastAPI server."""
    import uvicorn

    uvicorn.run("src.api.main:app", host="127.0.0.1", port=8000, reload=False)


def run_tui(ui: str = "textual"):
    """Run selected TUI runtime."""
    if ui == "rich":
        from src.tui.rich_app import JikaiTUI

        JikaiTUI().run()
        return

    from src.tui.textual_app import JikaiTextualApp

    JikaiTextualApp().run()


def main():
    parser = argparse.ArgumentParser(description="Jikai - Legal Hypothetical Generator")
    parser.add_argument("--api-only", action="store_true", help="Run API server only")
    parser.add_argument("--tui-only", action="store_true", help="Run TUI only")
    parser.add_argument("--both", action="store_true", help="Run both API and TUI")
    parser.add_argument(
        "--ui",
        choices=["rich", "textual"],
        default="textual",
        help="Select TUI runtime",
    )
    args = parser.parse_args()

    if args.api_only:
        run_api()
    elif args.tui_only:
        run_tui(ui=args.ui)
    elif args.both:
        api_thread = threading.Thread(target=run_api, daemon=True)
        api_thread.start()
        run_tui(ui=args.ui)
    else:
        run_tui(ui=args.ui)


if __name__ == "__main__":
    main()
