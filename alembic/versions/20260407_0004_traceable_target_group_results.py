"""traceable target group results and richer audit fields

Revision ID: 20260407_0004
Revises: 20260403_0003
Create Date: 2026-04-07 11:30:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260407_0004"
down_revision = "20260403_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("audit_logs", sa.Column("old_value_json", sa.JSON(), nullable=True))
    op.add_column("audit_logs", sa.Column("new_value_json", sa.JSON(), nullable=True))
    op.add_column("audit_logs", sa.Column("ip_address", sa.String(length=100), nullable=True))

    op.add_column("target_group_jobs", sa.Column("import_job_id", sa.Integer(), nullable=True))
    op.add_column("target_group_jobs", sa.Column("source_file_type", sa.String(length=20), nullable=False, server_default="excel"))
    op.add_column("target_group_jobs", sa.Column("uploaded_by", sa.String(length=100), nullable=True))
    op.add_column("target_group_jobs", sa.Column("parse_status", sa.String(length=20), nullable=False, server_default="pending"))
    op.add_column("target_group_jobs", sa.Column("match_status", sa.String(length=20), nullable=False, server_default="pending"))
    op.add_column("target_group_jobs", sa.Column("notes", sa.Text(), nullable=True))
    op.create_foreign_key(
        "fk_target_group_jobs_import_job_id",
        "target_group_jobs",
        "import_jobs",
        ["import_job_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_target_group_jobs_import_job_id", "target_group_jobs", ["import_job_id"])
    op.create_index("ix_target_group_jobs_parse_status", "target_group_jobs", ["parse_status"])
    op.create_index("ix_target_group_jobs_match_status", "target_group_jobs", ["match_status"])

    op.add_column("target_group_rows", sa.Column("parse_status", sa.String(length=20), nullable=False, server_default="pending"))
    op.add_column("target_group_rows", sa.Column("match_status", sa.String(length=20), nullable=True))
    op.add_column("target_group_rows", sa.Column("matched_patient_id", sa.Integer(), nullable=True))
    op.add_column("target_group_rows", sa.Column("confidence_flag", sa.String(length=30), nullable=True))
    op.add_column("target_group_rows", sa.Column("error_message", sa.Text(), nullable=True))
    op.create_foreign_key(
        "fk_target_group_rows_matched_patient_id",
        "target_group_rows",
        "patients",
        ["matched_patient_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_target_group_rows_match_status", "target_group_rows", ["match_status"])
    op.create_index("ix_target_group_rows_matched_patient_id", "target_group_rows", ["matched_patient_id"])

    op.add_column("target_group_results", sa.Column("disease_key", sa.String(length=100), nullable=True))
    op.add_column("target_group_results", sa.Column("disease_code", sa.String(length=100), nullable=True))
    op.add_column("target_group_results", sa.Column("disease_name", sa.String(length=255), nullable=True))
    op.add_column("target_group_results", sa.Column("result_status", sa.String(length=30), nullable=False, server_default="pending"))
    op.add_column("target_group_results", sa.Column("matched_disease_keys_json", sa.JSON(), nullable=False, server_default="[]"))
    op.add_column("target_group_results", sa.Column("matched_disease_labels_json", sa.JSON(), nullable=False, server_default="[]"))
    op.add_column("target_group_results", sa.Column("matched_service_items_json", sa.JSON(), nullable=False, server_default="[]"))
    op.add_column("target_group_results", sa.Column("query_filters_json", sa.JSON(), nullable=False, server_default="{}"))
    op.add_column(
        "target_group_results",
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.alter_column(
        "target_group_results",
        "years_since_latest_visit",
        existing_type=sa.Integer(),
        type_=sa.Numeric(10, 2),
        existing_nullable=True,
        postgresql_using="years_since_latest_visit::numeric(10,2)",
    )
    op.create_index("ix_target_group_results_disease_key", "target_group_results", ["disease_key"])

    op.execute("UPDATE target_group_jobs SET source_file_type = 'excel' WHERE source_file_type IS NULL")
    op.execute("UPDATE target_group_jobs SET parse_status = 'success' WHERE parse_status = 'pending'")
    op.execute("UPDATE target_group_jobs SET match_status = CASE WHEN status = 'matched' THEN 'success' ELSE 'pending' END")
    op.execute("UPDATE target_group_rows SET parse_status = CASE WHEN is_valid THEN 'success' ELSE 'failed' END")
    op.execute("UPDATE target_group_rows SET match_status = 'matched' WHERE matched_patient_id IS NOT NULL")
    op.execute(
        """
        UPDATE target_group_results
        SET result_status = CASE
            WHEN has_disease_history IS TRUE THEN 'history_found'
            WHEN has_disease_history IS FALSE THEN 'history_not_found'
            ELSE 'history_unknown'
        END
        """
    )

    op.alter_column("target_group_jobs", "source_file_type", server_default=None)
    op.alter_column("target_group_jobs", "parse_status", server_default=None)
    op.alter_column("target_group_jobs", "match_status", server_default=None)
    op.alter_column("target_group_rows", "parse_status", server_default=None)
    op.alter_column("target_group_results", "result_status", server_default=None)
    op.alter_column("target_group_results", "matched_disease_keys_json", server_default=None)
    op.alter_column("target_group_results", "matched_disease_labels_json", server_default=None)
    op.alter_column("target_group_results", "matched_service_items_json", server_default=None)
    op.alter_column("target_group_results", "query_filters_json", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_target_group_results_disease_key", table_name="target_group_results")
    op.alter_column(
        "target_group_results",
        "years_since_latest_visit",
        existing_type=sa.Numeric(10, 2),
        type_=sa.Integer(),
        existing_nullable=True,
        postgresql_using="ROUND(years_since_latest_visit)::integer",
    )
    for column in [
        "generated_at",
        "query_filters_json",
        "matched_service_items_json",
        "matched_disease_labels_json",
        "matched_disease_keys_json",
        "result_status",
        "disease_name",
        "disease_code",
        "disease_key",
    ]:
        op.drop_column("target_group_results", column)

    op.drop_index("ix_target_group_rows_matched_patient_id", table_name="target_group_rows")
    op.drop_index("ix_target_group_rows_match_status", table_name="target_group_rows")
    op.drop_constraint("fk_target_group_rows_matched_patient_id", "target_group_rows", type_="foreignkey")
    for column in ["error_message", "confidence_flag", "matched_patient_id", "match_status", "parse_status"]:
        op.drop_column("target_group_rows", column)

    op.drop_index("ix_target_group_jobs_match_status", table_name="target_group_jobs")
    op.drop_index("ix_target_group_jobs_parse_status", table_name="target_group_jobs")
    op.drop_index("ix_target_group_jobs_import_job_id", table_name="target_group_jobs")
    op.drop_constraint("fk_target_group_jobs_import_job_id", "target_group_jobs", type_="foreignkey")
    for column in ["notes", "match_status", "parse_status", "uploaded_by", "source_file_type", "import_job_id"]:
        op.drop_column("target_group_jobs", column)

    for column in ["ip_address", "new_value_json", "old_value_json"]:
        op.drop_column("audit_logs", column)
