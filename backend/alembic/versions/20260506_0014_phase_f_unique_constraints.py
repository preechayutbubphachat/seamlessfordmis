"""Phase F: unique constraints on linked-model tables for idempotent population.

Adds:
  - UNIQUE index on disease_screening_events.source_record_id  (each screening
    record maps to at most one event row)
  - UNIQUE index on person_identifiers (person_id, identifier_type, identifier_value)
    so PhaseFPopulationService can rely on ON CONFLICT without needing extra guards

These were omitted from 0013 because the tables were scaffold-only.  They are
required before PhaseFPopulationService can run safely.

Revision ID: 20260506_0014
Revises: 20260504_0013
Create Date: 2026-05-06
"""

from __future__ import annotations

from alembic import op


revision = "20260506_0014"
down_revision = "20260504_0013"
branch_labels = None
depends_on = None


def _has_index(index_name: str) -> bool:
    from sqlalchemy import inspect, text
    bind = op.get_bind()
    result = bind.execute(
        text("SELECT 1 FROM pg_indexes WHERE indexname = :n"),
        {"n": index_name},
    ).fetchone()
    return result is not None


def upgrade() -> None:
    # Unique: one event row per screening record.
    if not _has_index("uq_dse_source_record_id"):
        op.create_index(
            "uq_dse_source_record_id",
            "disease_screening_events",
            ["source_record_id"],
            unique=True,
        )

    # Unique: no duplicate (person, type, value) triplet in person_identifiers.
    if not _has_index("uq_person_identifiers_person_type_value"):
        op.create_index(
            "uq_person_identifiers_person_type_value",
            "person_identifiers",
            ["person_id", "identifier_type", "identifier_value"],
            unique=True,
        )


def downgrade() -> None:
    for idx in ["uq_dse_source_record_id", "uq_person_identifiers_person_type_value"]:
        if _has_index(idx):
            op.drop_index(idx)
