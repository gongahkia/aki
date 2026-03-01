"""CLI entry point for Jikai TUI/API."""

import argparse

from .app_runner import run


def main() -> None:
    parser = argparse.ArgumentParser(description="Jikai - Legal Hypothetical Generator")
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--tui-only",
        dest="mode",
        action="store_const",
        const="tui-only",
        help="Run only the selected TUI runtime.",
    )
    mode_group.add_argument(
        "--api-only",
        dest="mode",
        action="store_const",
        const="api-only",
        help="Run API-only mode without launching a TUI.",
    )
    mode_group.add_argument(
        "--both",
        dest="mode",
        action="store_const",
        const="both",
        help="Run API and TUI mode.",
    )
    parser.set_defaults(mode="tui-only")
    parser.add_argument(
        "--ui",
        choices=["rich", "textual"],
        default="rich",
        help="Select TUI runtime",
    )
    args = parser.parse_args()
    run(args.mode, ui=args.ui)


if __name__ == "__main__":
    main()
