"""add group type to disease mapping

Revision ID: 20260403_0003
Revises: 20260403_0002
Create Date: 2026-04-03 21:45:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260403_0003"
down_revision = "20260403_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "disease_mapping",
        sa.Column("group_type", sa.String(length=30), nullable=False, server_default="service"),
    )
    op.create_index("ix_disease_mapping_group_type", "disease_mapping", ["group_type"], unique=False)
    op.alter_column("disease_mapping", "group_type", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_disease_mapping_group_type", table_name="disease_mapping")
    op.drop_column("disease_mapping", "group_type")
