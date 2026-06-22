"""Phase E: add target_group_result_summaries cache table

Revision ID: 20260504_0012
Revises: 20260503_0011
Create Date: 2026-05-04
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260504_0012"
down_revision = "20260503_0011"
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    conn = op.get_bind()
    return conn.dialect.has_table(conn, name)


def _has_index(table: str, index: str) -> bool:
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM pg_indexes WHERE tablename = :t AND indexname = :i"
        ),
        {"t": table, "i": index},
    )
    return result.fetchone() is not None


def upgrade() -> None:
    if not _has_table("target_group_result_summaries"):
        op.create_table(
            "target_group_result_summaries",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column(
                "group_job_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("target_group_jobs.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("selected_service_hash", sa.String(64), nullable=False),
            sa.Column("selected_service_keys", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.Column("overdue_threshold_years", sa.Integer(), nullable=True),
            # Headcount aggregates
            sa.Column("total_target_people", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("valid_identifier_people", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("invalid_identifier_people", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("non_thai_nationality_people", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("insufficient_identity_people", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("outside_target_scope_people", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("review_required_identity_people", sa.Integer(), nullable=False, server_default="0"),
            # History coverage
            sa.Column("people_with_selected_history", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("people_without_selected_history", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("never_checked_people", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("checked_but_overdue_people", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("checked_and_within_threshold_people", sa.Integer(), nullable=False, server_default="0"),
            # Coverage
            sa.Column("coverage_percent", sa.Numeric(6, 2), nullable=False, server_default="0"),
            sa.Column(
                "generated_at",
                sa.DateTime(timezone=False),
                nullable=False,
                server_default=sa.text("now()"),
            ),
        )

    if not _has_index("target_group_result_summaries", "idx_tgrs_group_service_hash"):
        op.create_index(
            "idx_tgrs_group_service_hash",
            "target_group_result_summaries",
            ["group_job_id", "selected_service_hash"],
            unique=True,
        )


def downgrade() -> None:
    if _has_index("target_group_result_summaries", "idx_tgrs_group_service_hash"):
        op.drop_index("idx_tgrs_group_service_hash", table_name="target_group_result_summaries")
    if _has_table("target_group_result_summaries"):
        op.drop_table("target_group_result_summaries")
