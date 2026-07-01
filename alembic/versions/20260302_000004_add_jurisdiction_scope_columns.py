"""Add jurisdiction scope columns to generation history.

Revision ID: 20260302_000004
Revises: 20260301_000003
Create Date: 2026-03-02 00:00:00
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260302_000004"
down_revision = "20260301_000003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    result = bind.execute(sa.text("PRAGMA table_info(generation_history)"))
    columns = {row[1] for row in result.fetchall()}
    if "corpus_pack_key" not in columns:
        op.execute(
            "ALTER TABLE generation_history "
            "ADD COLUMN corpus_pack_key TEXT DEFAULT 'sg_tort'"
        )
    if "jurisdiction" not in columns:
        op.execute(
            "ALTER TABLE generation_history ADD COLUMN jurisdiction TEXT DEFAULT 'sg'"
        )
    if "subject" not in columns:
        op.execute(
            "ALTER TABLE generation_history ADD COLUMN subject TEXT DEFAULT 'tort'"
        )
    if "subtopics" not in columns:
        op.execute(
            "ALTER TABLE generation_history ADD COLUMN subtopics TEXT DEFAULT '[]'"
        )


def downgrade() -> None:
    # SQLite cannot drop columns portably without table rebuild; keep downgrade no-op.
    pass
