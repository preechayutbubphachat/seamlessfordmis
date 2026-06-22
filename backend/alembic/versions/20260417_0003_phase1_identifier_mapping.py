"""phase1 identifier mapping

Revision ID: 20260417_0003
Revises: 20260417_0002
Create Date: 2026-04-17 12:25:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260417_0003"
down_revision: str | None = "20260417_0002"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("staging_history_records", sa.Column("raw_person_identifier", sa.Text(), nullable=True))
    op.add_column("staging_history_records", sa.Column("raw_service_type", sa.Text(), nullable=True))
    op.add_column("staging_history_records", sa.Column("person_identifier_validation_status", sa.String(length=30), nullable=True))
    op.add_column("staging_history_records", sa.Column("visit_date_validation_status", sa.String(length=30), nullable=True))
    op.add_column("staging_history_records", sa.Column("service_validation_status", sa.String(length=30), nullable=True))
    op.add_column("staging_history_records", sa.Column("normalized_person_identifier", sa.Text(), nullable=True))
    op.add_column("staging_history_records", sa.Column("normalized_service_key", sa.Text(), nullable=True))

    op.add_column("diagnosis_history", sa.Column("raw_person_identifier", sa.Text(), nullable=True))
    op.add_column("diagnosis_history", sa.Column("raw_service_type", sa.Text(), nullable=True))
    op.add_column("diagnosis_history", sa.Column("normalized_person_identifier", sa.Text(), nullable=True))
    op.add_column("diagnosis_history", sa.Column("normalized_service_key", sa.Text(), nullable=True))

    op.add_column("target_group_rows", sa.Column("raw_cid", sa.Text(), nullable=True))
    op.add_column("target_group_rows", sa.Column("normalized_cid", sa.Text(), nullable=True))
    op.add_column("target_group_rows", sa.Column("cid_validation_status", sa.String(length=30), nullable=True))


def downgrade() -> None:
    op.drop_column("target_group_rows", "cid_validation_status")
    op.drop_column("target_group_rows", "normalized_cid")
    op.drop_column("target_group_rows", "raw_cid")

    op.drop_column("diagnosis_history", "normalized_service_key")
    op.drop_column("diagnosis_history", "normalized_person_identifier")
    op.drop_column("diagnosis_history", "raw_service_type")
    op.drop_column("diagnosis_history", "raw_person_identifier")

    op.drop_column("staging_history_records", "normalized_service_key")
    op.drop_column("staging_history_records", "normalized_person_identifier")
    op.drop_column("staging_history_records", "service_validation_status")
    op.drop_column("staging_history_records", "visit_date_validation_status")
    op.drop_column("staging_history_records", "person_identifier_validation_status")
    op.drop_column("staging_history_records", "raw_service_type")
    op.drop_column("staging_history_records", "raw_person_identifier")
