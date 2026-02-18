"""Jikai TUI Console and Logging setup."""

import logging
import os
from rich.console import Console

console = Console()

# Logging setup
LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_PATH = os.path.join(LOG_DIR, "tui.log")

_fh = logging.FileHandler(LOG_PATH, mode="w", encoding="utf-8")
_fh.setFormatter(
    logging.Formatter("%(asctime)s  %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
)

tlog = logging.getLogger("jikai.tui")
tlog.setLevel(logging.INFO)
tlog.addHandler(_fh)

def setup_logging(level_name: str = "INFO"):
    """Configure logging level."""
    level = getattr(logging, level_name.upper(), logging.INFO)
    tlog.setLevel(level)
