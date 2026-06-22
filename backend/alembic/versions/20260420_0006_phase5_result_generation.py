"""phase5 result generation

Revision ID: 20260420_0006
Revises: 20260417_0005
Create Date: 2026-04-20 10:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260420_0006"
down_revision: str | None = "20260417_0005"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("target_group_results", sa.Column("target_row_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("target_group_results", sa.Column("normalized_cid", sa.Text(), nullable=True))
    op.add_column("target_group_results", sa.Column("full_name", sa.Text(), nullable=True))
    op.add_column("target_group_results", sa.Column("age", sa.Integer(), nullable=True))
    op.add_column("target_group_results", sa.Column("sex", sa.String(length=20), nullable=True))
    op.add_column("target_group_results", sa.Column("has_selected_service", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("target_group_results", sa.Column("matching_record_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("target_group_results", sa.Column("matched_service_keys", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("target_group_results", sa.Column("selected_service_keys", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("target_group_results", sa.Column("selected_service_hash", sa.String(length=64), nullable=True))
    op.add_column("target_group_results", sa.Column("warning_message", sa.Text(), nullable=True))

    op.alter_column("target_group_results", "patient_id", existing_type=postgresql.UUID(as_uuid=True), nullable=True)

    op.create_foreign_key(
        "fk_target_group_results_target_row_id",
        "target_group_results",
        "target_group_rows",
        ["target_row_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.create_index("idx_target_group_results_target_row_id", "target_group_results", ["target_row_id"], unique=False)
    op.create_index("idx_target_group_results_normalized_cid", "target_group_results", ["normalized_cid"], unique=False)
    op.create_index("idx_target_group_results_selected_service_hash", "target_group_results", ["selected_service_hash"], unique=False)

    op.execute("UPDATE target_group_results SET has_selected_service = CASE WHEN visit_count > 0 THEN true ELSE false END")
    op.execute("UPDATE target_group_results SET matching_record_count = visit_count")
    op.execute("UPDATE target_group_results SET selected_service_keys = '[]'::jsonb WHERE selected_service_keys IS NULL")
    op.execute("UPDATE target_group_results SET selected_service_hash = '' WHERE selected_service_hash IS NULL")

    op.alter_column("target_group_results", "selected_service_keys", nullable=False)
    op.alter_column("target_group_results", "selected_service_hash", nullable=False)

    op.alter_column("target_group_results", "has_selected_service", server_default=None)
    op.alter_column("target_group_results", "matching_record_count", server_default=None)


def downgrade() -> None:
    op.drop_index("idx_target_group_results_selected_service_hash", table_name="target_group_results")
    op.drop_index("idx_target_group_results_normalized_cid", table_name="target_group_results")
    op.drop_index("idx_target_group_results_target_row_id", table_name="target_group_results")
    op.drop_constraint("fk_target_group_results_target_row_id", "target_group_results", type_="foreignkey")

    op.alter_column("target_group_results", "patient_id", existing_type=postgresql.UUID(as_uuid=True), nullable=False)

    op.drop_column("target_group_results", "warning_message")
    op.drop_column("target_group_results", "selected_service_hash")
    op.drop_column("target_group_results", "selected_service_keys")
    op.drop_column("target_group_results", "matched_service_keys")
    op.drop_column("target_group_results", "matching_record_count")
    op.drop_column("target_group_results", "has_selected_service")
    op.drop_column("target_group_results", "sex")
    op.drop_column("target_group_results", "age")
    op.drop_column("target_group_results", "full_name")
    op.drop_column("target_group_results", "normalized_cid")
    op.drop_column("target_group_results", "target_row_id")
