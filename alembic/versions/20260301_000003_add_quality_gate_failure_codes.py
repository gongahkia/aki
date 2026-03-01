"""Add quality gate failure reason code storage to generation history.

Revision ID: 20260301_000003
Revises: 20260228_000002
Create Date: 2026-03-01 22:00:00
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260301_000003"
down_revision = "20260228_000002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    result = bind.execute(sa.text("PRAGMA table_info(generation_history)"))
    columns = {row[1] for row in result.fetchall()}
    if "quality_gate_failure_reasons" not in columns:
        op.execute(
            """
            ALTER TABLE generation_history
            ADD COLUMN quality_gate_failure_reasons TEXT
            """
        )


def downgrade() -> None:
    # SQLite column drops require table rebuild; keep schema backward-compatible.
    pass
