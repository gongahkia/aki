"""Alembic migration runner for SQLite schema upgrades."""

from pathlib import Path

import structlog
from alembic import command
from alembic.config import Config

from ..config import settings

logger = structlog.get_logger(__name__)


def _database_url() -> str:
    db_path = Path(settings.database_path).expanduser()
    if not db_path.is_absolute():
        db_path = Path.cwd() / db_path
    return f"sqlite:///{db_path}"


def run_database_migrations():
    """Run Alembic migrations to head revision."""
    repo_root = Path(__file__).resolve().parents[2]
    alembic_dir = repo_root / "alembic"
    versions_dir = alembic_dir / "versions"
    if not versions_dir.exists():
        logger.warning("Skipping migrations: alembic versions directory missing")
        return

    config = Config()
    config.set_main_option("script_location", str(alembic_dir))
    config.set_main_option("sqlalchemy.url", _database_url())
    command.upgrade(config, "head")
    logger.info("Database migrations applied", script_location=str(alembic_dir))
