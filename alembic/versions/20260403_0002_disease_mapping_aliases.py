"""allow multiple raw aliases per normalized disease key

Revision ID: 20260403_0002
Revises: 20260403_0001
Create Date: 2026-04-03 21:10:00
"""

from alembic import op


revision = "20260403_0002"
down_revision = "20260403_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE disease_mapping DROP CONSTRAINT IF EXISTS disease_mapping_normalized_disease_key_key")
    op.execute("DROP INDEX IF EXISTS ix_disease_mapping_normalized_disease_key")
    op.create_index("ix_disease_mapping_normalized_disease_key", "disease_mapping", ["normalized_disease_key"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_disease_mapping_normalized_disease_key", table_name="disease_mapping")
    op.create_index("ix_disease_mapping_normalized_disease_key", "disease_mapping", ["normalized_disease_key"], unique=True)
    op.create_unique_constraint(
        "disease_mapping_normalized_disease_key_key",
        "disease_mapping",
        ["normalized_disease_key"],
    )
