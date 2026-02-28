"""Create base SQLite schema for generations and reports.

Revision ID: 20260228_000001
Revises:
Create Date: 2026-02-28 23:30:00
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260228_000001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS generation_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            topics TEXT NOT NULL,
            law_domain TEXT,
            number_parties INTEGER,
            complexity_level TEXT,
            hypothetical TEXT,
            analysis TEXT,
            generation_time REAL,
            validation_passed BOOLEAN,
            quality_score REAL,
            request_data TEXT,
            response_data TEXT,
            parent_generation_id INTEGER,
            retry_reason TEXT,
            retry_attempt INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_timestamp
        ON generation_history(timestamp DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_topics
        ON generation_history(topics)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_generation_history_parent_generation_id
        ON generation_history(parent_generation_id)
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS generation_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            generation_id INTEGER NOT NULL,
            issue_types TEXT NOT NULL,
            comment TEXT,
            is_locked BOOLEAN NOT NULL DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (generation_id) REFERENCES generation_history(id) ON DELETE CASCADE
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_generation_reports_generation_id
        ON generation_reports(generation_id)
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS generation_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id INTEGER NOT NULL,
            generation_id INTEGER NOT NULL,
            feedback_text TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (report_id) REFERENCES generation_reports(id) ON DELETE CASCADE,
            FOREIGN KEY (generation_id) REFERENCES generation_history(id) ON DELETE CASCADE
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_generation_feedback_report_id
        ON generation_feedback(report_id)
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS migration_state (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS generation_feedback")
    op.execute("DROP TABLE IF EXISTS generation_reports")
    op.execute("DROP TABLE IF EXISTS generation_history")
    op.execute("DROP TABLE IF EXISTS migration_state")
