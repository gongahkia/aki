"""CLI entry point for Jikai TUI/API."""

import argparse
import threading


def run_api():
    """Run FastAPI server."""
    import uvicorn

    uvicorn.run("src.api.main:app", host="0.0.0.0", port=8000, reload=False)


def run_tui():
    """Run Textual TUI."""
    from src.tui.app import JikaiApp

    app = JikaiApp()
    app.run()


def main():
    parser = argparse.ArgumentParser(description="Jikai - Legal Hypothetical Generator")
    parser.add_argument("--api-only", action="store_true", help="Run API server only")
    parser.add_argument("--tui-only", action="store_true", help="Run TUI only")
    parser.add_argument("--both", action="store_true", help="Run both API and TUI")
    args = parser.parse_args()

    if args.api_only:
        run_api()
    elif args.tui_only:
        run_tui()
    elif args.both:
        api_thread = threading.Thread(target=run_api, daemon=True)
        api_thread.start()
        run_tui()
    else:
        run_tui()  # default to TUI


if __name__ == "__main__":
    main()
