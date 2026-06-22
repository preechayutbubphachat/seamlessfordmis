"""phase5 result generation compatibility

Revision ID: 20260420_0007
Revises: 20260420_0006
Create Date: 2026-04-20 16:25:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260420_0007"
down_revision: str | None = "20260420_0006"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # Phase 5 stores the selected multi-service context in JSONB fields.
    # Keep the legacy disease_key column for single-service compatibility,
    # but allow NULL so multi-service result sets do not fail at insert time.
    op.alter_column("target_group_results", "disease_key", existing_type=sa.Text(), nullable=True)


def downgrade() -> None:
    op.alter_column("target_group_results", "disease_key", existing_type=sa.Text(), nullable=False)
