"""add multi-file provenance and pdf-safe import fields

Revision ID: 20260417_0002
Revises: 20260407_0001
Create Date: 2026-04-17 16:30:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260417_0002"
down_revision = "20260407_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("import_jobs", sa.Column("source_set_hash", sa.String(length=64), nullable=True))
    op.add_column("import_jobs", sa.Column("source_file_count", sa.Integer(), nullable=False, server_default="1"))
    op.create_index("idx_import_jobs_source_set_hash", "import_jobs", ["source_set_hash"])

    op.create_table(
        "source_files",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("import_job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("import_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_name", sa.Text(), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=True),
        sa.Column("file_type", sa.String(length=20), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("source_modified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("parse_status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("row_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("warning_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("idx_source_files_import_job_id", "source_files", ["import_job_id"])
    op.create_index("idx_source_files_sha256", "source_files", ["sha256"])
    op.create_index("idx_source_files_file_type", "source_files", ["file_type"])

    op.add_column("staging_history_records", sa.Column("source_file_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("staging_history_records", sa.Column("source_file_name", sa.Text(), nullable=True))
    op.add_column("staging_history_records", sa.Column("source_row_no", sa.Integer(), nullable=True))
    op.add_column("staging_history_records", sa.Column("confidence_flag", sa.String(length=30), nullable=True))
    op.create_foreign_key(
        "fk_staging_history_source_file_id",
        "staging_history_records",
        "source_files",
        ["source_file_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("idx_staging_history_source_file_id", "staging_history_records", ["source_file_id"])

    op.add_column("diagnosis_history", sa.Column("source_file_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("diagnosis_history", sa.Column("source_file_name", sa.Text(), nullable=True))
    op.create_foreign_key(
        "fk_diagnosis_history_source_file_id",
        "diagnosis_history",
        "source_files",
        ["source_file_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("idx_diagnosis_history_source_file_id", "diagnosis_history", ["source_file_id"])

    op.add_column("target_group_jobs", sa.Column("source_set_hash", sa.String(length=64), nullable=True))
    op.add_column("target_group_jobs", sa.Column("source_file_count", sa.Integer(), nullable=False, server_default="1"))
    op.create_index("idx_target_group_jobs_source_set_hash", "target_group_jobs", ["source_set_hash"])

    op.create_table(
        "target_group_job_files",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("group_job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("target_group_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_name", sa.Text(), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=True),
        sa.Column("file_type", sa.String(length=20), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("source_modified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("parse_status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("row_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("warning_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("idx_target_group_job_files_group_job_id", "target_group_job_files", ["group_job_id"])
    op.create_index("idx_target_group_job_files_sha256", "target_group_job_files", ["sha256"])
    op.create_index("idx_target_group_job_files_file_type", "target_group_job_files", ["file_type"])

    op.add_column("target_group_rows", sa.Column("source_file_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("target_group_rows", sa.Column("source_file_name", sa.Text(), nullable=True))
    op.add_column("target_group_rows", sa.Column("source_row_no", sa.Integer(), nullable=True))
    op.add_column("target_group_rows", sa.Column("validation_status", sa.String(length=30), nullable=False, server_default="pending"))
    op.create_foreign_key(
        "fk_target_group_rows_source_file_id",
        "target_group_rows",
        "target_group_job_files",
        ["source_file_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("idx_target_group_rows_source_file_id", "target_group_rows", ["source_file_id"])


def downgrade() -> None:
    op.drop_index("idx_target_group_rows_source_file_id", table_name="target_group_rows")
    op.drop_constraint("fk_target_group_rows_source_file_id", "target_group_rows", type_="foreignkey")
    op.drop_column("target_group_rows", "validation_status")
    op.drop_column("target_group_rows", "source_row_no")
    op.drop_column("target_group_rows", "source_file_name")
    op.drop_column("target_group_rows", "source_file_id")

    op.drop_index("idx_target_group_job_files_file_type", table_name="target_group_job_files")
    op.drop_index("idx_target_group_job_files_sha256", table_name="target_group_job_files")
    op.drop_index("idx_target_group_job_files_group_job_id", table_name="target_group_job_files")
    op.drop_table("target_group_job_files")

    op.drop_index("idx_target_group_jobs_source_set_hash", table_name="target_group_jobs")
    op.drop_column("target_group_jobs", "source_file_count")
    op.drop_column("target_group_jobs", "source_set_hash")

    op.drop_index("idx_diagnosis_history_source_file_id", table_name="diagnosis_history")
    op.drop_constraint("fk_diagnosis_history_source_file_id", "diagnosis_history", type_="foreignkey")
    op.drop_column("diagnosis_history", "source_file_name")
    op.drop_column("diagnosis_history", "source_file_id")

    op.drop_index("idx_staging_history_source_file_id", table_name="staging_history_records")
    op.drop_constraint("fk_staging_history_source_file_id", "staging_history_records", type_="foreignkey")
    op.drop_column("staging_history_records", "confidence_flag")
    op.drop_column("staging_history_records", "source_row_no")
    op.drop_column("staging_history_records", "source_file_name")
    op.drop_column("staging_history_records", "source_file_id")

    op.drop_index("idx_source_files_file_type", table_name="source_files")
    op.drop_index("idx_source_files_sha256", table_name="source_files")
    op.drop_index("idx_source_files_import_job_id", table_name="source_files")
    op.drop_table("source_files")

    op.drop_index("idx_import_jobs_source_set_hash", table_name="import_jobs")
    op.drop_column("import_jobs", "source_file_count")
    op.drop_column("import_jobs", "source_set_hash")
