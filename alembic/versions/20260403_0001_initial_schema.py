"""initial schema

Revision ID: 20260403_0001
Revises:
Create Date: 2026-04-03 16:10:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260403_0001"
down_revision = None
branch_labels = None
depends_on = None


import_job_status = postgresql.ENUM("pending", "running", "completed", "failed", name="importjobstatus", create_type=False)
target_group_status = postgresql.ENUM("uploaded", "confirmed", "matched", "failed", name="targetgroupstatus", create_type=False)
match_method = postgresql.ENUM("pid", "citizen_id", "hn", "name_birth_date", "name_only", "unmatched", name="matchmethod", create_type=False)
match_status = postgresql.ENUM("matched", "needs_review", "unmatched", "ambiguous", name="matchstatus", create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    import_job_status.create(bind, checkfirst=True)
    target_group_status.create(bind, checkfirst=True)
    match_method.create(bind, checkfirst=True)
    match_status.create(bind, checkfirst=True)

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor", sa.String(length=100), nullable=False),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("entity_type", sa.String(length=100), nullable=False),
        sa.Column("entity_id", sa.String(length=100), nullable=True),
        sa.Column("details_json", sa.JSON(), nullable=False),
        sa.Column("correlation_id", sa.String(length=100), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_entity_type", "audit_logs", ["entity_type"])
    op.create_index("ix_audit_logs_entity_id", "audit_logs", ["entity_id"])
    op.create_index("ix_audit_logs_correlation_id", "audit_logs", ["correlation_id"])

    op.create_table(
        "disease_mapping",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("normalized_disease_key", sa.String(length=100), nullable=False),
        sa.Column("diagnosis_code", sa.String(length=50), nullable=True),
        sa.Column("disease_name_raw", sa.String(length=255), nullable=True),
        sa.Column("disease_group_label", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("normalized_disease_key"),
    )
    op.create_index("ix_disease_mapping_normalized_disease_key", "disease_mapping", ["normalized_disease_key"])
    op.create_index("ix_disease_mapping_diagnosis_code", "disease_mapping", ["diagnosis_code"])
    op.create_index("ix_disease_mapping_disease_name_raw", "disease_mapping", ["disease_name_raw"])

    op.create_table(
        "import_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_type", sa.String(length=50), nullable=False),
        sa.Column("status", import_job_status, nullable=False),
        sa.Column("source_filename", sa.String(length=255), nullable=False),
        sa.Column("source_path", sa.Text(), nullable=False),
        sa.Column("source_hash_sha256", sa.String(length=64), nullable=False),
        sa.Column("source_manifest_hash_sha256", sa.String(length=64), nullable=True),
        sa.Column("source_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("source_file_count", sa.Integer(), nullable=False),
        sa.Column("source_modified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_rows", sa.Integer(), nullable=True),
        sa.Column("imported_rows", sa.Integer(), nullable=True),
        sa.Column("error_rows", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_import_jobs_source_hash_sha256", "import_jobs", ["source_hash_sha256"])
    op.create_index("ix_import_jobs_source_manifest_hash_sha256", "import_jobs", ["source_manifest_hash_sha256"])

    op.create_table(
        "patients",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("pid", sa.String(length=50), nullable=True),
        sa.Column("citizen_id", sa.String(length=20), nullable=True),
        sa.Column("hn", sa.String(length=50), nullable=True),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("normalized_name", sa.String(length=255), nullable=True),
        sa.Column("birth_date", sa.Date(), nullable=True),
        sa.Column("source_import_job_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("pid", name="uq_patients_pid"),
        sa.UniqueConstraint("citizen_id", name="uq_patients_citizen_id"),
        sa.UniqueConstraint("hn", name="uq_patients_hn"),
    )
    op.create_index("ix_patients_pid", "patients", ["pid"])
    op.create_index("ix_patients_citizen_id", "patients", ["citizen_id"])
    op.create_index("ix_patients_hn", "patients", ["hn"])
    op.create_index("ix_patients_full_name", "patients", ["full_name"])
    op.create_index("ix_patients_normalized_name", "patients", ["normalized_name"])
    op.create_index("ix_patients_birth_date", "patients", ["birth_date"])

    op.create_table(
        "target_group_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_name", sa.String(length=255), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("stored_path", sa.Text(), nullable=False),
        sa.Column("file_hash_sha256", sa.String(length=64), nullable=False),
        sa.Column("status", target_group_status, nullable=False),
        sa.Column("total_rows", sa.Integer(), nullable=True),
        sa.Column("valid_rows", sa.Integer(), nullable=True),
        sa.Column("invalid_rows", sa.Integer(), nullable=True),
        sa.Column("review_rows", sa.Integer(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("confirmed_at", sa.Date(), nullable=True),
        sa.Column("matched_at", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_target_group_jobs_file_hash_sha256", "target_group_jobs", ["file_hash_sha256"])

    op.create_table(
        "import_job_source_files",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("import_job_id", sa.Integer(), sa.ForeignKey("import_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("file_hash_sha256", sa.String(length=64), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("file_modified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_import_job_source_files_import_job_id", "import_job_source_files", ["import_job_id"])
    op.create_index("ix_import_job_source_files_file_hash_sha256", "import_job_source_files", ["file_hash_sha256"])

    op.create_table(
        "staging_history_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("import_job_id", sa.Integer(), sa.ForeignKey("import_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("source_filename", sa.String(length=255), nullable=False),
        sa.Column("source_sheet_name", sa.String(length=100), nullable=False),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("pid", sa.String(length=50), nullable=True),
        sa.Column("citizen_id", sa.String(length=20), nullable=True),
        sa.Column("hn", sa.String(length=50), nullable=True),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("birth_date", sa.Date(), nullable=True),
        sa.Column("visit_date", sa.Date(), nullable=True),
        sa.Column("diagnosis_code", sa.String(length=50), nullable=True),
        sa.Column("disease_name_raw", sa.String(length=255), nullable=True),
        sa.Column("normalized_disease_key", sa.String(length=100), nullable=True),
        sa.Column("validation_errors", sa.JSON(), nullable=False),
        sa.Column("is_valid", sa.Boolean(), nullable=False),
        sa.Column("review_required", sa.Boolean(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    for name, cols in [
        ("ix_staging_history_records_import_job_id", ["import_job_id"]),
        ("ix_staging_history_records_pid", ["pid"]),
        ("ix_staging_history_records_citizen_id", ["citizen_id"]),
        ("ix_staging_history_records_hn", ["hn"]),
        ("ix_staging_history_records_full_name", ["full_name"]),
        ("ix_staging_history_records_diagnosis_code", ["diagnosis_code"]),
        ("ix_staging_history_records_normalized_disease_key", ["normalized_disease_key"]),
    ]:
        op.create_index(name, "staging_history_records", cols)

    op.create_table(
        "target_group_rows",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("target_group_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("pid", sa.String(length=50), nullable=True),
        sa.Column("citizen_id", sa.String(length=20), nullable=True),
        sa.Column("hn", sa.String(length=50), nullable=True),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("birth_date", sa.Date(), nullable=True),
        sa.Column("is_valid", sa.Boolean(), nullable=False),
        sa.Column("validation_errors", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    for name, cols in [
        ("ix_target_group_rows_job_id", ["job_id"]),
        ("ix_target_group_rows_pid", ["pid"]),
        ("ix_target_group_rows_citizen_id", ["citizen_id"]),
        ("ix_target_group_rows_hn", ["hn"]),
        ("ix_target_group_rows_full_name", ["full_name"]),
    ]:
        op.create_index(name, "target_group_rows", cols)

    op.create_table(
        "diagnosis_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("import_job_id", sa.Integer(), sa.ForeignKey("import_jobs.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("visit_date", sa.Date(), nullable=True),
        sa.Column("diagnosis_code", sa.String(length=50), nullable=True),
        sa.Column("disease_name_raw", sa.String(length=255), nullable=True),
        sa.Column("normalized_disease_key", sa.String(length=100), nullable=True),
        sa.Column("encounter_type", sa.String(length=100), nullable=True),
        sa.Column("provider_name", sa.String(length=255), nullable=True),
        sa.Column("source_filename", sa.String(length=255), nullable=False),
        sa.Column("source_sheet_name", sa.String(length=100), nullable=False),
        sa.Column("source_row_number", sa.Integer(), nullable=False),
        sa.Column("raw_payload_json", sa.JSON(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    for name, cols in [
        ("ix_diagnosis_history_patient_id", ["patient_id"]),
        ("ix_diagnosis_history_import_job_id", ["import_job_id"]),
        ("ix_diagnosis_history_visit_date", ["visit_date"]),
        ("ix_diagnosis_history_diagnosis_code", ["diagnosis_code"]),
        ("ix_diagnosis_history_normalized_disease_key", ["normalized_disease_key"]),
    ]:
        op.create_index(name, "diagnosis_history", cols)

    op.create_table(
        "target_group_results",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("target_group_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_group_row_id", sa.Integer(), sa.ForeignKey("target_group_rows.id", ondelete="CASCADE"), nullable=False),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id", ondelete="SET NULL"), nullable=True),
        sa.Column("match_method", match_method, nullable=False),
        sa.Column("match_status", match_status, nullable=False),
        sa.Column("confidence_score", sa.String(length=20), nullable=True),
        sa.Column("selected_disease_key", sa.String(length=100), nullable=True),
        sa.Column("has_disease_history", sa.Boolean(), nullable=True),
        sa.Column("latest_visit_date", sa.Date(), nullable=True),
        sa.Column("visit_count", sa.Integer(), nullable=True),
        sa.Column("days_since_latest_visit", sa.Integer(), nullable=True),
        sa.Column("years_since_latest_visit", sa.Integer(), nullable=True),
        sa.Column("flags_json", sa.JSON(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    for name, cols in [
        ("ix_target_group_results_job_id", ["job_id"]),
        ("ix_target_group_results_target_group_row_id", ["target_group_row_id"]),
        ("ix_target_group_results_patient_id", ["patient_id"]),
        ("ix_target_group_results_selected_disease_key", ["selected_disease_key"]),
    ]:
        op.create_index(name, "target_group_results", cols)


def downgrade() -> None:
    for table, indexes in [
        ("target_group_results", [
            "ix_target_group_results_selected_disease_key",
            "ix_target_group_results_patient_id",
            "ix_target_group_results_target_group_row_id",
            "ix_target_group_results_job_id",
        ]),
        ("diagnosis_history", [
            "ix_diagnosis_history_normalized_disease_key",
            "ix_diagnosis_history_diagnosis_code",
            "ix_diagnosis_history_visit_date",
            "ix_diagnosis_history_import_job_id",
            "ix_diagnosis_history_patient_id",
        ]),
        ("target_group_rows", [
            "ix_target_group_rows_full_name",
            "ix_target_group_rows_hn",
            "ix_target_group_rows_citizen_id",
            "ix_target_group_rows_pid",
            "ix_target_group_rows_job_id",
        ]),
        ("staging_history_records", [
            "ix_staging_history_records_normalized_disease_key",
            "ix_staging_history_records_diagnosis_code",
            "ix_staging_history_records_full_name",
            "ix_staging_history_records_hn",
            "ix_staging_history_records_citizen_id",
            "ix_staging_history_records_pid",
            "ix_staging_history_records_import_job_id",
        ]),
        ("import_job_source_files", [
            "ix_import_job_source_files_file_hash_sha256",
            "ix_import_job_source_files_import_job_id",
        ]),
        ("target_group_jobs", ["ix_target_group_jobs_file_hash_sha256"]),
        ("patients", [
            "ix_patients_birth_date",
            "ix_patients_normalized_name",
            "ix_patients_full_name",
            "ix_patients_hn",
            "ix_patients_citizen_id",
            "ix_patients_pid",
        ]),
        ("import_jobs", [
            "ix_import_jobs_source_manifest_hash_sha256",
            "ix_import_jobs_source_hash_sha256",
        ]),
        ("disease_mapping", [
            "ix_disease_mapping_disease_name_raw",
            "ix_disease_mapping_diagnosis_code",
            "ix_disease_mapping_normalized_disease_key",
        ]),
        ("audit_logs", [
            "ix_audit_logs_correlation_id",
            "ix_audit_logs_entity_id",
            "ix_audit_logs_entity_type",
            "ix_audit_logs_action",
        ]),
    ]:
        for index in indexes:
            op.drop_index(index, table_name=table)
        op.drop_table(table)

    bind = op.get_bind()
    match_status.drop(bind, checkfirst=True)
    match_method.drop(bind, checkfirst=True)
    target_group_status.drop(bind, checkfirst=True)
    import_job_status.drop(bind, checkfirst=True)
