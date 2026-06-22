"""add normalization_version to target_group_result_summaries

Lets the app flag cached results that were generated with an older
classification/normalization logic version so the UI can prompt the user to
regenerate (never auto-regenerate). Nullable: pre-existing rows read as NULL
and are treated as stale.

Revision ID: 20260616_0016
Revises: 20260508_0015
Create Date: 2026-06-16
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260616_0016"
down_revision = "20260508_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "target_group_result_summaries",
        sa.Column("normalization_version", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("target_group_result_summaries", "normalization_version")
