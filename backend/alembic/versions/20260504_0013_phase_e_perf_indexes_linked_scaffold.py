"""Phase E: performance composite indexes + linked model scaffold tables

Adds composite indexes on the hot query paths identified in performance
profiling, and creates the empty scaffold tables for the future unified
linked database model (Phase F / issue #9).  The scaffold tables carry no
data yet — they exist so the schema is reviewable and the foreign-key graph
is established before data migration begins.

Revision ID: 20260504_0013
Revises: 20260504_0012
Create Date: 2026-05-04
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260504_0013"
down_revision = "20260504_0012"
branch_labels = None
depends_on = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _has_index(table: str, index: str) -> bool:
    conn = op.get_bind()
    result = conn.execute(
        sa.text("SELECT 1 FROM pg_indexes WHERE tablename = :t AND indexname = :i"),
        {"t": table, "i": index},
    )
    return result.fetchone() is not None


def _has_table(name: str) -> bool:
    conn = op.get_bind()
    return conn.dialect.has_table(conn, name)


# ---------------------------------------------------------------------------
# Upgrade
# ---------------------------------------------------------------------------

def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Composite performance indexes
    # ------------------------------------------------------------------

    # target_group_results: filter by status within a group (view= param)
    if not _has_index("target_group_results", "idx_tgr_group_result_status"):
        op.create_index(
            "idx_tgr_group_result_status",
            "target_group_results",
            ["group_job_id", "result_status"],
        )

    # target_group_results: filter by has_selected_service within a group
    if not _has_index("target_group_results", "idx_tgr_group_has_history"):
        op.create_index(
            "idx_tgr_group_has_history",
            "target_group_results",
            ["group_job_id", "has_selected_service"],
        )

    # disease_screening_records: two-column lookup by person + service key
    if not _has_index("disease_screening_records", "idx_dsr_identifier_service_key"):
        op.create_index(
            "idx_dsr_identifier_service_key",
            "disease_screening_records",
            ["normalized_person_identifier", "normalized_service_key"],
        )

    # target_group_history_rows: lookup by group + cid + service key
    if not _has_index("target_group_history_rows", "idx_tghr_group_cid_service"):
        op.create_index(
            "idx_tghr_group_cid_service",
            "target_group_history_rows",
            ["group_job_id", "normalized_cid", "normalized_service_key"],
        )

    # target_group_history_rows: lookup by group + name when cid absent
    if not _has_index("target_group_history_rows", "idx_tghr_group_name_service"):
        op.create_index(
            "idx_tghr_group_name_service",
            "target_group_history_rows",
            ["group_job_id", "normalized_full_name", "normalized_service_key"],
        )

    # ------------------------------------------------------------------
    # 2. Linked model scaffold tables (Phase F — empty schema only)
    # ------------------------------------------------------------------

    # person_master: one row per deduplicated real-world person.
    # canonical_person_key mirrors the value stored on TargetGroupResult.
    if not _has_table("person_master"):
        op.create_table(
            "person_master",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("canonical_person_key", sa.Text(), nullable=False, unique=True),
            sa.Column("display_name", sa.Text(), nullable=True),
            sa.Column("primary_cid", sa.String(13), nullable=True),
            sa.Column("primary_birth_date", sa.Date(), nullable=True),
            sa.Column("primary_sex", sa.String(20), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=False),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=False),
                nullable=False,
                server_default=sa.text("now()"),
            ),
        )
        op.create_index(
            "idx_person_master_canonical_key",
            "person_master",
            ["canonical_person_key"],
            unique=True,
        )
        op.create_index(
            "idx_person_master_cid",
            "person_master",
            ["primary_cid"],
        )

    # person_identifiers: all known identifier values for a person.
    if not _has_table("person_identifiers"):
        op.create_table(
            "person_identifiers",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column(
                "person_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("person_master.id", ondelete="CASCADE"),
                nullable=False,
            ),
            # identifier_type: "citizen_id" | "name_birthdate" | "name_address"
            sa.Column("identifier_type", sa.String(30), nullable=False),
            sa.Column("identifier_value", sa.Text(), nullable=False),
            sa.Column("confidence", sa.String(20), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=False),
                nullable=False,
                server_default=sa.text("now()"),
            ),
        )
        op.create_index(
            "idx_person_identifiers_person_id",
            "person_identifiers",
            ["person_id"],
        )
        op.create_index(
            "idx_person_identifiers_value",
            "person_identifiers",
            ["identifier_type", "identifier_value"],
        )

    # disease_screening_events: normalized event rows from the screening DB,
    # linked to person_master once the linkage migration runs.
    if not _has_table("disease_screening_events"):
        op.create_table(
            "disease_screening_events",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column(
                "person_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("person_master.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "source_record_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("disease_screening_records.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("normalized_service_key", sa.Text(), nullable=True),
            sa.Column("event_date", sa.Date(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=False),
                nullable=False,
                server_default=sa.text("now()"),
            ),
        )
        op.create_index(
            "idx_dse_person_id",
            "disease_screening_events",
            ["person_id"],
        )
        op.create_index(
            "idx_dse_person_service",
            "disease_screening_events",
            ["person_id", "normalized_service_key"],
        )

    # target_group_membership: links target_group_rows to person_master.
    if not _has_table("target_group_membership"):
        op.create_table(
            "target_group_membership",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column(
                "person_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("person_master.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "target_row_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("target_group_rows.id", ondelete="CASCADE"),
                nullable=False,
                unique=True,
            ),
            sa.Column(
                "group_job_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("target_group_jobs.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=False),
                nullable=False,
                server_default=sa.text("now()"),
            ),
        )
        op.create_index(
            "idx_tgm_person_id",
            "target_group_membership",
            ["person_id"],
        )
        op.create_index(
            "idx_tgm_group_job_id",
            "target_group_membership",
            ["group_job_id"],
        )


# ---------------------------------------------------------------------------
# Downgrade
# ---------------------------------------------------------------------------

def downgrade() -> None:
    # Drop scaffold tables (order respects FK dependencies)
    for tbl in ["target_group_membership", "disease_screening_events", "person_identifiers", "person_master"]:
        if _has_table(tbl):
            op.drop_table(tbl)

    # Drop composite performance indexes
    for table, idx in [
        ("target_group_history_rows", "idx_tghr_group_name_service"),
        ("target_group_history_rows", "idx_tghr_group_cid_service"),
        ("disease_screening_records", "idx_dsr_identifier_service_key"),
        ("target_group_results", "idx_tgr_group_has_history"),
        ("target_group_results", "idx_tgr_group_result_status"),
    ]:
        if _has_index(table, idx):
            op.drop_index(idx, table_name=table)
