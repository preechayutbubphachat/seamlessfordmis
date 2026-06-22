"""phase2 disease screening pipeline

Revision ID: 20260417_0004
Revises: 20260417_0003
Create Date: 2026-04-17 13:15:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op


revision: str = "20260417_0004"
down_revision: str | None = "20260417_0003"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("import_jobs", sa.Column("parsed_rows", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("import_jobs", sa.Column("valid_rows", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("import_jobs", sa.Column("invalid_rows", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("import_jobs", sa.Column("warning_rows", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("import_jobs", sa.Column("merged_rows", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("import_jobs", sa.Column("skipped_rows", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("import_jobs", sa.Column("duplicate_identifier_count", sa.Integer(), nullable=False, server_default="0"))

    op.add_column("staging_history_records", sa.Column("raw_hcode", sa.Text(), nullable=True))
    op.add_column("staging_history_records", sa.Column("raw_transaction_id", sa.Text(), nullable=True))
    op.add_column("staging_history_records", sa.Column("raw_rep_no", sa.Text(), nullable=True))
    op.add_column("staging_history_records", sa.Column("warning_message", sa.Text(), nullable=True))
    op.alter_column("staging_history_records", "person_identifier_validation_status", new_column_name="identifier_validation_status")
    op.alter_column("staging_history_records", "visit_date_validation_status", new_column_name="date_validation_status")

    op.create_table(
        "disease_screening_records",
        sa.Column("source_import_job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_file_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_file_name", sa.Text(), nullable=True),
        sa.Column("source_row_no", sa.Integer(), nullable=True),
        sa.Column("raw_person_identifier", sa.Text(), nullable=False),
        sa.Column("normalized_person_identifier", sa.Text(), nullable=False),
        sa.Column("full_name", sa.Text(), nullable=True),
        sa.Column("normalized_full_name", sa.Text(), nullable=True),
        sa.Column("raw_service_type", sa.Text(), nullable=False),
        sa.Column("normalized_service_key", sa.Text(), nullable=False),
        sa.Column("visit_date", sa.Date(), nullable=False),
        sa.Column("hcode", sa.Text(), nullable=True),
        sa.Column("transaction_id", sa.Text(), nullable=True),
        sa.Column("rep_no", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["source_file_id"], ["source_files.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_import_job_id"], ["import_jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_disease_screening_records_import_job_id", "disease_screening_records", ["source_import_job_id"], unique=False)
    op.create_index("idx_disease_screening_records_source_file_id", "disease_screening_records", ["source_file_id"], unique=False)
    op.create_index("idx_disease_screening_records_identifier", "disease_screening_records", ["normalized_person_identifier"], unique=False)
    op.create_index("idx_disease_screening_records_service_key", "disease_screening_records", ["normalized_service_key"], unique=False)
    op.create_index("idx_disease_screening_records_visit_date", "disease_screening_records", ["visit_date"], unique=False)
    op.create_index(
        "uq_disease_screening_records_source_row",
        "disease_screening_records",
        ["source_import_job_id", "source_file_id", "source_row_no"],
        unique=True,
    )

    op.alter_column("import_jobs", "parsed_rows", server_default=None)
    op.alter_column("import_jobs", "valid_rows", server_default=None)
    op.alter_column("import_jobs", "invalid_rows", server_default=None)
    op.alter_column("import_jobs", "warning_rows", server_default=None)
    op.alter_column("import_jobs", "merged_rows", server_default=None)
    op.alter_column("import_jobs", "skipped_rows", server_default=None)
    op.alter_column("import_jobs", "duplicate_identifier_count", server_default=None)


def downgrade() -> None:
    op.drop_index("uq_disease_screening_records_source_row", table_name="disease_screening_records")
    op.drop_index("idx_disease_screening_records_visit_date", table_name="disease_screening_records")
    op.drop_index("idx_disease_screening_records_service_key", table_name="disease_screening_records")
    op.drop_index("idx_disease_screening_records_identifier", table_name="disease_screening_records")
    op.drop_index("idx_disease_screening_records_source_file_id", table_name="disease_screening_records")
    op.drop_index("idx_disease_screening_records_import_job_id", table_name="disease_screening_records")
    op.drop_table("disease_screening_records")

    op.alter_column("staging_history_records", "date_validation_status", new_column_name="visit_date_validation_status")
    op.alter_column("staging_history_records", "identifier_validation_status", new_column_name="person_identifier_validation_status")
    op.drop_column("staging_history_records", "warning_message")
    op.drop_column("staging_history_records", "raw_rep_no")
    op.drop_column("staging_history_records", "raw_transaction_id")
    op.drop_column("staging_history_records", "raw_hcode")

    op.drop_column("import_jobs", "duplicate_identifier_count")
    op.drop_column("import_jobs", "skipped_rows")
    op.drop_column("import_jobs", "merged_rows")
    op.drop_column("import_jobs", "warning_rows")
    op.drop_column("import_jobs", "invalid_rows")
    op.drop_column("import_jobs", "valid_rows")
    op.drop_column("import_jobs", "parsed_rows")
