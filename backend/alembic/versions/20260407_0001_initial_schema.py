"""initial hospital group history schema

Revision ID: 20260407_0001
Revises:
Create Date: 2026-04-07 12:10:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260407_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto";')

    op.create_table(
        "import_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("source_file_name", sa.Text(), nullable=False),
        sa.Column("source_file_path", sa.Text(), nullable=True),
        sa.Column("source_file_hash", sa.String(length=64), nullable=False),
        sa.Column("source_file_size", sa.BigInteger(), nullable=True),
        sa.Column("source_file_modified_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("total_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("success_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", sa.Text(), nullable=True),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("idx_import_jobs_source_type", "import_jobs", ["source_type"])
    op.create_index("idx_import_jobs_status", "import_jobs", ["status"])
    op.create_index("idx_import_jobs_hash", "import_jobs", ["source_file_hash"])

    op.create_table(
        "patients",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("pid", sa.Text(), nullable=True),
        sa.Column("citizen_id", sa.Text(), nullable=True),
        sa.Column("hn", sa.Text(), nullable=True),
        sa.Column("full_name", sa.Text(), nullable=False),
        sa.Column("birth_date", sa.Date(), nullable=True),
        sa.Column("sex", sa.String(length=20), nullable=True),
        sa.Column("source_import_job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("import_jobs.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("uq_patients_pid", "patients", ["pid"], unique=True, postgresql_where=sa.text("pid IS NOT NULL"))
    op.create_index("uq_patients_citizen_id", "patients", ["citizen_id"], unique=True, postgresql_where=sa.text("citizen_id IS NOT NULL"))
    op.create_index("idx_patients_hn", "patients", ["hn"])
    op.create_index("idx_patients_full_name", "patients", ["full_name"])
    op.create_index("idx_patients_birth_date", "patients", ["birth_date"])

    op.create_table(
        "staging_history_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("import_job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("import_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("row_no", sa.Integer(), nullable=False),
        sa.Column("raw_pid", sa.Text(), nullable=True),
        sa.Column("raw_citizen_id", sa.Text(), nullable=True),
        sa.Column("raw_hn", sa.Text(), nullable=True),
        sa.Column("raw_full_name", sa.Text(), nullable=True),
        sa.Column("raw_birth_date", sa.Text(), nullable=True),
        sa.Column("raw_visit_date", sa.Text(), nullable=True),
        sa.Column("raw_diagnosis_code", sa.Text(), nullable=True),
        sa.Column("raw_diagnosis_name", sa.Text(), nullable=True),
        sa.Column("raw_department", sa.Text(), nullable=True),
        sa.Column("raw_doctor_name", sa.Text(), nullable=True),
        sa.Column("parse_status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("validation_status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("normalized_pid", sa.Text(), nullable=True),
        sa.Column("normalized_citizen_id", sa.Text(), nullable=True),
        sa.Column("normalized_hn", sa.Text(), nullable=True),
        sa.Column("normalized_full_name", sa.Text(), nullable=True),
        sa.Column("normalized_birth_date", sa.Date(), nullable=True),
        sa.Column("normalized_visit_date", sa.Date(), nullable=True),
        sa.Column("normalized_diagnosis_code", sa.Text(), nullable=True),
        sa.Column("normalized_diagnosis_name", sa.Text(), nullable=True),
        sa.Column("normalized_disease_key", sa.Text(), nullable=True),
        sa.Column("raw_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("idx_staging_history_import_job_id", "staging_history_records", ["import_job_id"])
    op.create_index("idx_staging_history_validation_status", "staging_history_records", ["validation_status"])

    op.create_table(
        "diagnosis_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("patients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("visit_date", sa.Date(), nullable=False),
        sa.Column("diagnosis_code", sa.Text(), nullable=True),
        sa.Column("diagnosis_name", sa.Text(), nullable=True),
        sa.Column("normalized_disease_key", sa.Text(), nullable=True),
        sa.Column("department", sa.Text(), nullable=True),
        sa.Column("doctor_name", sa.Text(), nullable=True),
        sa.Column("source_import_job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("import_jobs.id"), nullable=True),
        sa.Column("source_row_no", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("idx_diagnosis_history_patient_id", "diagnosis_history", ["patient_id"])
    op.create_index("idx_diagnosis_history_visit_date", "diagnosis_history", ["visit_date"])
    op.create_index("idx_diagnosis_history_diagnosis_code", "diagnosis_history", ["diagnosis_code"])
    op.create_index("idx_diagnosis_history_disease_key", "diagnosis_history", ["normalized_disease_key"])
    op.create_index("idx_diagnosis_history_patient_disease_visit", "diagnosis_history", ["patient_id", "normalized_disease_key", "visit_date"])

    op.create_table(
        "target_group_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("import_job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("import_jobs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("group_name", sa.Text(), nullable=False),
        sa.Column("source_file_name", sa.Text(), nullable=False),
        sa.Column("source_file_type", sa.String(length=20), nullable=False),
        sa.Column("source_file_hash", sa.String(length=64), nullable=False),
        sa.Column("uploaded_by", sa.Text(), nullable=True),
        sa.Column("parse_status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("match_status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("idx_target_group_jobs_parse_status", "target_group_jobs", ["parse_status"])
    op.create_index("idx_target_group_jobs_match_status", "target_group_jobs", ["match_status"])

    op.create_table(
        "target_group_rows",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("group_job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("target_group_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("row_no", sa.Integer(), nullable=False),
        sa.Column("raw_pid", sa.Text(), nullable=True),
        sa.Column("raw_citizen_id", sa.Text(), nullable=True),
        sa.Column("raw_hn", sa.Text(), nullable=True),
        sa.Column("raw_full_name", sa.Text(), nullable=True),
        sa.Column("raw_birth_date", sa.Text(), nullable=True),
        sa.Column("normalized_pid", sa.Text(), nullable=True),
        sa.Column("normalized_citizen_id", sa.Text(), nullable=True),
        sa.Column("normalized_hn", sa.Text(), nullable=True),
        sa.Column("normalized_full_name", sa.Text(), nullable=True),
        sa.Column("normalized_birth_date", sa.Date(), nullable=True),
        sa.Column("parse_status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("match_status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("matched_patient_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("patients.id", ondelete="SET NULL"), nullable=True),
        sa.Column("confidence_flag", sa.String(length=30), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("raw_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("idx_target_group_rows_group_job_id", "target_group_rows", ["group_job_id"])
    op.create_index("idx_target_group_rows_match_status", "target_group_rows", ["match_status"])
    op.create_index("idx_target_group_rows_matched_patient_id", "target_group_rows", ["matched_patient_id"])

    op.create_table(
        "target_group_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("group_job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("target_group_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("patients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("disease_key", sa.Text(), nullable=False),
        sa.Column("disease_code", sa.Text(), nullable=True),
        sa.Column("disease_name", sa.Text(), nullable=True),
        sa.Column("last_visit_date", sa.Date(), nullable=True),
        sa.Column("visit_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("days_since_last_visit", sa.Integer(), nullable=True),
        sa.Column("years_since_last_visit", sa.Numeric(10, 2), nullable=True),
        sa.Column("result_status", sa.String(length=30), nullable=False, server_default="generated"),
        sa.Column("generated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_target_group_results_group_job_id", "target_group_results", ["group_job_id"])
    op.create_index("idx_target_group_results_patient_id", "target_group_results", ["patient_id"])
    op.create_index("idx_target_group_results_disease_key", "target_group_results", ["disease_key"])

    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("actor", sa.Text(), nullable=True),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_id", sa.Text(), nullable=False),
        sa.Column("old_value_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("new_value_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("ip_address", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("idx_audit_logs_entity_type", "audit_logs", ["entity_type"])
    op.create_index("idx_audit_logs_entity_id", "audit_logs", ["entity_id"])
    op.create_index("idx_audit_logs_created_at", "audit_logs", ["created_at"])

    op.create_table(
        "disease_mapping",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("raw_code", sa.Text(), nullable=True),
        sa.Column("raw_name", sa.Text(), nullable=True),
        sa.Column("normalized_key", sa.Text(), nullable=False),
        sa.Column("normalized_label", sa.Text(), nullable=False),
        sa.Column("icd10_code", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("idx_disease_mapping_raw_code", "disease_mapping", ["raw_code"])
    op.create_index("idx_disease_mapping_raw_name", "disease_mapping", ["raw_name"])
    op.create_index("idx_disease_mapping_normalized_key", "disease_mapping", ["normalized_key"])


def downgrade() -> None:
    for table, indexes in [
        ("disease_mapping", ["idx_disease_mapping_normalized_key", "idx_disease_mapping_raw_name", "idx_disease_mapping_raw_code"]),
        ("audit_logs", ["idx_audit_logs_created_at", "idx_audit_logs_entity_id", "idx_audit_logs_entity_type"]),
        ("target_group_results", ["idx_target_group_results_disease_key", "idx_target_group_results_patient_id", "idx_target_group_results_group_job_id"]),
        ("target_group_rows", ["idx_target_group_rows_matched_patient_id", "idx_target_group_rows_match_status", "idx_target_group_rows_group_job_id"]),
        ("target_group_jobs", ["idx_target_group_jobs_match_status", "idx_target_group_jobs_parse_status"]),
        ("diagnosis_history", ["idx_diagnosis_history_patient_disease_visit", "idx_diagnosis_history_disease_key", "idx_diagnosis_history_diagnosis_code", "idx_diagnosis_history_visit_date", "idx_diagnosis_history_patient_id"]),
        ("staging_history_records", ["idx_staging_history_validation_status", "idx_staging_history_import_job_id"]),
        ("patients", ["idx_patients_birth_date", "idx_patients_full_name", "idx_patients_hn", "uq_patients_citizen_id", "uq_patients_pid"]),
        ("import_jobs", ["idx_import_jobs_hash", "idx_import_jobs_status", "idx_import_jobs_source_type"]),
    ]:
        for index in indexes:
            op.drop_index(index, table_name=table)
        op.drop_table(table)
