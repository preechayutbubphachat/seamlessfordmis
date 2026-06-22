"""add source_set_hash to target_group_result_summaries

Revision ID: 20260508_0015
Revises: 20260506_0014
Create Date: 2026-05-08
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260508_0015"
down_revision = "20260506_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "target_group_result_summaries",
        sa.Column("source_set_hash", sa.String(64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("target_group_result_summaries", "source_set_hash")
