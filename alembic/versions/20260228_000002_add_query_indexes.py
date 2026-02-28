"""Ensure query indexes for history, reports, and lineage lookups.

Revision ID: 20260228_000002
Revises: 20260228_000001
Create Date: 2026-02-28 23:55:00
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260228_000002"
down_revision = "20260228_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_generation_history_timestamp
        ON generation_history(timestamp DESC)
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
        CREATE INDEX IF NOT EXISTS idx_generation_reports_generation_id
        ON generation_reports(generation_id)
        """
    )
    # Remove legacy generic index name if present.
    op.execute("DROP INDEX IF EXISTS idx_timestamp")


def downgrade() -> None:
    # Keep fallback legacy index for compatibility with older schema expectations.
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_timestamp
        ON generation_history(timestamp DESC)
        """
    )
    op.execute("DROP INDEX IF EXISTS idx_generation_history_timestamp")
    op.execute("DROP INDEX IF EXISTS idx_generation_history_parent_generation_id")
    op.execute("DROP INDEX IF EXISTS idx_generation_reports_generation_id")
