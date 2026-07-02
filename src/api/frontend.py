"""Frontend file locations served by the API."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_ROOT = PROJECT_ROOT / "frontend"
DEMO_FRONTEND_ROOT = FRONTEND_ROOT / "demo"


def demo_page_path(filename: str) -> Path:
    return DEMO_FRONTEND_ROOT / filename
