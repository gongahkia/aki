"""CLI entry point for Jikai TUI/API."""

import argparse

from .app_runner import run


def main():
    parser = argparse.ArgumentParser(description="Jikai - Legal Hypothetical Generator")
    parser.add_argument("--api-only", action="store_true", help="Run API server only")
    parser.add_argument("--tui-only", action="store_true", help="Run TUI only")
    parser.add_argument("--both", action="store_true", help="Run both API and TUI")
    parser.add_argument(
        "--ui",
        choices=["rich", "textual"],
        default="rich",
        help="Select TUI runtime",
    )
    args = parser.parse_args()

    if args.api_only:
        run("api-only", ui=args.ui)
    elif args.tui_only:
        run("tui-only", ui=args.ui)
    elif args.both:
        run("both", ui=args.ui)
    else:
        run("default", ui=args.ui)


if __name__ == "__main__":
    main()
