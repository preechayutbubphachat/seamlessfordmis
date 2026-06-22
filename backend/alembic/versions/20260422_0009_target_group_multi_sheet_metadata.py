"""target group multi-sheet metadata

Revision ID: 20260422_0009
Revises: 20260420_0008
Create Date: 2026-04-22 12:40:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260422_0009"
down_revision: str | None = "20260420_0008"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def _has_table(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _has_column(table_name: str, column_name: str) -> bool:
    if not _has_table(table_name):
        return False
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def _has_index(table_name: str, index_name: str) -> bool:
    if not _has_table(table_name):
        return False
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return index_name in {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    if not _has_table("target_group_sheets"):
        op.create_table(
            "target_group_sheets",
            sa.Column("group_job_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("source_file_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("sheet_name", sa.Text(), nullable=False),
            sa.Column("sheet_index", sa.Integer(), nullable=False),
            sa.Column("sheet_type", sa.Text(), nullable=False),
            sa.Column("row_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("column_names_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("classification_confidence", sa.Numeric(4, 2), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["group_job_id"], ["target_group_jobs.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["source_file_id"], ["target_group_job_files.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.alter_column("target_group_sheets", "row_count", server_default=None)

    if not _has_index("target_group_sheets", "idx_target_group_sheets_group_job_id"):
        op.create_index("idx_target_group_sheets_group_job_id", "target_group_sheets", ["group_job_id"], unique=False)
    if not _has_index("target_group_sheets", "idx_target_group_sheets_source_file_id"):
        op.create_index("idx_target_group_sheets_source_file_id", "target_group_sheets", ["source_file_id"], unique=False)
    if not _has_index("target_group_sheets", "idx_target_group_sheets_sheet_type"):
        op.create_index("idx_target_group_sheets_sheet_type", "target_group_sheets", ["sheet_type"], unique=False)

    if not _has_table("target_group_history_rows"):
        op.create_table(
            "target_group_history_rows",
            sa.Column("group_job_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("source_file_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("source_sheet_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("source_file_name", sa.Text(), nullable=True),
            sa.Column("source_sheet_name", sa.Text(), nullable=True),
            sa.Column("source_row_no", sa.Integer(), nullable=True),
            sa.Column("raw_cid", sa.Text(), nullable=True),
            sa.Column("normalized_cid", sa.Text(), nullable=True),
            sa.Column("raw_full_name", sa.Text(), nullable=True),
            sa.Column("normalized_full_name", sa.Text(), nullable=True),
            sa.Column("raw_birth_date", sa.Text(), nullable=True),
            sa.Column("normalized_birth_date", sa.Date(), nullable=True),
            sa.Column("raw_address", sa.Text(), nullable=True),
            sa.Column("normalized_address", sa.Text(), nullable=True),
            sa.Column("raw_service_label", sa.Text(), nullable=True),
            sa.Column("raw_service_type", sa.Text(), nullable=True),
            sa.Column("normalized_service_key", sa.Text(), nullable=True),
            sa.Column("raw_visit_date", sa.Text(), nullable=True),
            sa.Column("normalized_visit_date", sa.Date(), nullable=True),
            sa.Column("raw_icd10", sa.Text(), nullable=True),
            sa.Column("raw_result", sa.Text(), nullable=True),
            sa.Column("raw_hpv", sa.Text(), nullable=True),
            sa.Column("raw_hospital", sa.Text(), nullable=True),
            sa.Column("raw_doctor", sa.Text(), nullable=True),
            sa.Column("raw_note", sa.Text(), nullable=True),
            sa.Column("parse_status", sa.String(length=30), nullable=False, server_default="pending"),
            sa.Column("validation_status", sa.String(length=30), nullable=False, server_default="pending"),
            sa.Column("identifier_validation_status", sa.String(length=30), nullable=True),
            sa.Column("date_validation_status", sa.String(length=30), nullable=True),
            sa.Column("service_validation_status", sa.String(length=30), nullable=True),
            sa.Column("warning_message", sa.Text(), nullable=True),
            sa.Column("raw_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["group_job_id"], ["target_group_jobs.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["source_file_id"], ["target_group_job_files.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["source_sheet_id"], ["target_group_sheets.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.alter_column("target_group_history_rows", "parse_status", server_default=None)
        op.alter_column("target_group_history_rows", "validation_status", server_default=None)
    else:
        if not _has_column("target_group_history_rows", "source_sheet_id"):
            op.add_column(
                "target_group_history_rows",
                sa.Column("source_sheet_id", postgresql.UUID(as_uuid=True), nullable=True),
            )
        if not _has_column("target_group_history_rows", "raw_birth_date"):
            op.add_column("target_group_history_rows", sa.Column("raw_birth_date", sa.Text(), nullable=True))
        if not _has_column("target_group_history_rows", "normalized_birth_date"):
            op.add_column("target_group_history_rows", sa.Column("normalized_birth_date", sa.Date(), nullable=True))
        if not _has_column("target_group_history_rows", "raw_address"):
            op.add_column("target_group_history_rows", sa.Column("raw_address", sa.Text(), nullable=True))
        if not _has_column("target_group_history_rows", "normalized_address"):
            op.add_column("target_group_history_rows", sa.Column("normalized_address", sa.Text(), nullable=True))
        if not _has_column("target_group_history_rows", "raw_service_label"):
            op.add_column("target_group_history_rows", sa.Column("raw_service_label", sa.Text(), nullable=True))
        op.create_foreign_key(
            "fk_tg_history_rows_source_sheet_id",
            "target_group_history_rows",
            "target_group_sheets",
            ["source_sheet_id"],
            ["id"],
            ondelete="SET NULL",
        )

    for index_name, columns in (
        ("idx_target_group_history_rows_group_job_id", ["group_job_id"]),
        ("idx_target_group_history_rows_source_file_id", ["source_file_id"]),
        ("idx_target_group_history_rows_source_sheet_id", ["source_sheet_id"]),
        ("idx_target_group_history_rows_source_sheet_name", ["source_sheet_name"]),
        ("idx_target_group_history_rows_normalized_cid", ["normalized_cid"]),
        ("idx_target_group_history_rows_normalized_full_name", ["normalized_full_name"]),
        ("idx_target_group_history_rows_service_key", ["normalized_service_key"]),
        ("idx_target_group_history_rows_visit_date", ["normalized_visit_date"]),
    ):
        if not _has_index("target_group_history_rows", index_name):
            op.create_index(index_name, "target_group_history_rows", columns, unique=False)


def downgrade() -> None:
    if _has_table("target_group_history_rows"):
        for index_name in (
            "idx_target_group_history_rows_visit_date",
            "idx_target_group_history_rows_service_key",
            "idx_target_group_history_rows_normalized_full_name",
            "idx_target_group_history_rows_normalized_cid",
            "idx_target_group_history_rows_source_sheet_name",
            "idx_target_group_history_rows_source_sheet_id",
            "idx_target_group_history_rows_source_file_id",
            "idx_target_group_history_rows_group_job_id",
        ):
            if _has_index("target_group_history_rows", index_name):
                op.drop_index(index_name, table_name="target_group_history_rows")

        if _has_column("target_group_history_rows", "source_sheet_id"):
            op.drop_constraint(
                "fk_tg_history_rows_source_sheet_id",
                "target_group_history_rows",
                type_="foreignkey",
            )
            for column_name in (
                "raw_service_label",
                "normalized_address",
                "raw_address",
                "normalized_birth_date",
                "raw_birth_date",
                "source_sheet_id",
            ):
                if _has_column("target_group_history_rows", column_name):
                    op.drop_column("target_group_history_rows", column_name)

    if _has_table("target_group_sheets"):
        for index_name in (
            "idx_target_group_sheets_sheet_type",
            "idx_target_group_sheets_source_file_id",
            "idx_target_group_sheets_group_job_id",
        ):
            if _has_index("target_group_sheets", index_name):
                op.drop_index(index_name, table_name="target_group_sheets")
        op.drop_table("target_group_sheets")
