"""phase10 state persistence matching overdue support

Revision ID: 20260420_0008
Revises: 20260420_0007
Create Date: 2026-04-20 20:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260420_0008"
down_revision: str | None = "20260420_0007"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("target_group_rows", sa.Column("raw_target_history_labels", sa.Text(), nullable=True))
    op.add_column("target_group_rows", sa.Column("raw_target_history_note", sa.Text(), nullable=True))
    op.add_column("target_group_rows", sa.Column("raw_target_history_last_visit_date", sa.Text(), nullable=True))
    op.add_column(
        "target_group_rows",
        sa.Column("normalized_target_history_service_keys", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column("target_group_rows", sa.Column("normalized_target_history_last_visit_date", sa.Date(), nullable=True))
    op.add_column("target_group_rows", sa.Column("match_method", sa.String(length=40), nullable=True))
    op.add_column("target_group_rows", sa.Column("matched_identifier_basis", sa.Text(), nullable=True))
    op.add_column("target_group_rows", sa.Column("matched_name_basis", sa.Text(), nullable=True))
    op.create_index("idx_target_group_rows_normalized_full_name", "target_group_rows", ["normalized_full_name"], unique=False)
    op.create_index(
        "idx_disease_screening_records_normalized_full_name",
        "disease_screening_records",
        ["normalized_full_name"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_disease_screening_records_normalized_full_name", table_name="disease_screening_records")
    op.drop_index("idx_target_group_rows_normalized_full_name", table_name="target_group_rows")
    op.drop_column("target_group_rows", "matched_name_basis")
    op.drop_column("target_group_rows", "matched_identifier_basis")
    op.drop_column("target_group_rows", "match_method")
    op.drop_column("target_group_rows", "normalized_target_history_last_visit_date")
    op.drop_column("target_group_rows", "normalized_target_history_service_keys")
    op.drop_column("target_group_rows", "raw_target_history_last_visit_date")
    op.drop_column("target_group_rows", "raw_target_history_note")
    op.drop_column("target_group_rows", "raw_target_history_labels")
