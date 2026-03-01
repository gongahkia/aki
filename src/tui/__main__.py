"""CLI entry point for Jikai TUI/API."""

import argparse

from .app_runner import run


def main():
    parser = argparse.ArgumentParser(description="Jikai - Legal Hypothetical Generator")
    parser.add_argument(
        "--ui",
        choices=["rich"],
        default="rich",
        help="Select TUI runtime",
    )
    args = parser.parse_args()
    run("tui-only", ui=args.ui)


if __name__ == "__main__":
    main()
