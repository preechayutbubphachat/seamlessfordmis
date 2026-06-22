"""phase3 target group pipeline

Revision ID: 20260417_0005
Revises: 20260417_0004
Create Date: 2026-04-17 15:45:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260417_0005"
down_revision: str | None = "20260417_0004"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("target_group_jobs", sa.Column("total_rows", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("target_group_jobs", sa.Column("parsed_rows", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("target_group_jobs", sa.Column("valid_rows", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("target_group_jobs", sa.Column("invalid_rows", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("target_group_jobs", sa.Column("missing_cid_rows", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("target_group_jobs", sa.Column("duplicate_cid_rows", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("target_group_jobs", sa.Column("warning_rows", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("target_group_jobs", sa.Column("failed_rows", sa.Integer(), nullable=False, server_default="0"))

    op.add_column("target_group_job_files", sa.Column("parse_error_summary", sa.Text(), nullable=True))

    op.add_column("target_group_rows", sa.Column("raw_age", sa.Text(), nullable=True))
    op.add_column("target_group_rows", sa.Column("raw_sex", sa.Text(), nullable=True))
    op.add_column("target_group_rows", sa.Column("normalized_age", sa.Integer(), nullable=True))
    op.add_column("target_group_rows", sa.Column("normalized_sex", sa.String(length=20), nullable=True))
    op.add_column("target_group_rows", sa.Column("duplicate_status", sa.String(length=30), nullable=True))
    op.add_column("target_group_rows", sa.Column("warning_message", sa.Text(), nullable=True))

    op.create_index("idx_target_group_rows_normalized_cid", "target_group_rows", ["normalized_cid"], unique=False)
    op.create_index("idx_target_group_rows_duplicate_status", "target_group_rows", ["duplicate_status"], unique=False)

    op.alter_column("target_group_jobs", "total_rows", server_default=None)
    op.alter_column("target_group_jobs", "parsed_rows", server_default=None)
    op.alter_column("target_group_jobs", "valid_rows", server_default=None)
    op.alter_column("target_group_jobs", "invalid_rows", server_default=None)
    op.alter_column("target_group_jobs", "missing_cid_rows", server_default=None)
    op.alter_column("target_group_jobs", "duplicate_cid_rows", server_default=None)
    op.alter_column("target_group_jobs", "warning_rows", server_default=None)
    op.alter_column("target_group_jobs", "failed_rows", server_default=None)


def downgrade() -> None:
    op.drop_index("idx_target_group_rows_duplicate_status", table_name="target_group_rows")
    op.drop_index("idx_target_group_rows_normalized_cid", table_name="target_group_rows")

    op.drop_column("target_group_rows", "warning_message")
    op.drop_column("target_group_rows", "duplicate_status")
    op.drop_column("target_group_rows", "normalized_sex")
    op.drop_column("target_group_rows", "normalized_age")
    op.drop_column("target_group_rows", "raw_sex")
    op.drop_column("target_group_rows", "raw_age")

    op.drop_column("target_group_job_files", "parse_error_summary")

    op.drop_column("target_group_jobs", "failed_rows")
    op.drop_column("target_group_jobs", "warning_rows")
    op.drop_column("target_group_jobs", "duplicate_cid_rows")
    op.drop_column("target_group_jobs", "missing_cid_rows")
    op.drop_column("target_group_jobs", "invalid_rows")
    op.drop_column("target_group_jobs", "valid_rows")
    op.drop_column("target_group_jobs", "parsed_rows")
    op.drop_column("target_group_jobs", "total_rows")
