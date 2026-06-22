"""Phase D: add person-level consolidation fields to target_group_results

Revision ID: 20260503_0011
Revises: 20260503_0010
Create Date: 2026-05-03

WHY
---
Phase D stores canonical_person_key, person_link_status, review_required, and
duplicate_reason on each TargetGroupResult row so that:

1. get_results() can look up the PersonResultContext by canonical_person_key
   instead of re-deriving the primary row at query time, eliminating a class
   of "wrong primary row" bugs that caused empty provenance in the response.

2. DB-level filtering on review_required and person_link_status becomes
   possible without reloading all target_group_rows on every request.

3. The identity confidence for each person result is auditable in the DB.

All columns are nullable / have safe defaults so existing rows continue to work
(they just get NULL for the new fields until re-generated).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260503_0011"
down_revision: str | None = "20260503_0010"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_TABLE = "target_group_results"


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return column in {col["name"] for col in inspector.get_columns(table)}


def _has_index(table: str, index: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return index in {idx["name"] for idx in inspector.get_indexes(table)}


def upgrade() -> None:
    if not _has_column(_TABLE, "canonical_person_key"):
        op.add_column(
            _TABLE,
            sa.Column("canonical_person_key", sa.Text(), nullable=True),
        )

    if not _has_column(_TABLE, "person_link_status"):
        op.add_column(
            _TABLE,
            sa.Column("person_link_status", sa.String(40), nullable=True),
        )

    if not _has_column(_TABLE, "review_required"):
        op.add_column(
            _TABLE,
            sa.Column(
                "review_required",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
        )

    if not _has_column(_TABLE, "duplicate_reason"):
        op.add_column(
            _TABLE,
            sa.Column("duplicate_reason", sa.Text(), nullable=True),
        )

    # Composite indexes for DB-level filtering
    if not _has_index(_TABLE, "idx_target_group_results_group_review"):
        op.create_index(
            "idx_target_group_results_group_review",
            _TABLE,
            ["group_job_id", "review_required"],
        )

    if not _has_index(_TABLE, "idx_target_group_results_group_link_status"):
        op.create_index(
            "idx_target_group_results_group_link_status",
            _TABLE,
            ["group_job_id", "person_link_status"],
        )

    if not _has_index(_TABLE, "idx_target_group_results_canonical_key"):
        op.create_index(
            "idx_target_group_results_canonical_key",
            _TABLE,
            ["group_job_id", "canonical_person_key"],
        )


def downgrade() -> None:
    for idx in (
        "idx_target_group_results_canonical_key",
        "idx_target_group_results_group_link_status",
        "idx_target_group_results_group_review",
    ):
        if _has_index(_TABLE, idx):
            op.drop_index(idx, table_name=_TABLE)

    for col in ("duplicate_reason", "review_required", "person_link_status", "canonical_person_key"):
        if _has_column(_TABLE, col):
            op.drop_column(_TABLE, col)
