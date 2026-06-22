"""composite index on target_group_history_rows (group_job_id, normalized_service_key)

Revision ID: 20260503_0010
Revises: 20260422_0009
Create Date: 2026-05-03

WHY
---
The result generation service queries target_group_history_rows with:
    WHERE group_job_id = :gid AND normalized_service_key IN (...)

Without a composite index the query planner must choose between the two
separate single-column indexes and then filter the other in memory, which
is slow for large target groups.  A composite index on (group_job_id,
normalized_service_key) lets Postgres satisfy the full predicate from one
index scan.

A second composite index on (group_job_id, normalized_cid) speeds up the
matching look-up in _collect_target_group_history_matches which iterates
over candidate CIDs for each person row.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260503_0010"
down_revision: str | None = "20260422_0009"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def _has_index(table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return index_name in {idx["name"] for idx in inspector.get_indexes(table_name)}


def upgrade() -> None:
    # Composite index for the primary result-generation query:
    # WHERE group_job_id = :gid AND normalized_service_key IN (...)
    if not _has_index(
        "target_group_history_rows",
        "idx_tg_history_rows_job_service_key",
    ):
        op.create_index(
            "idx_tg_history_rows_job_service_key",
            "target_group_history_rows",
            ["group_job_id", "normalized_service_key"],
            unique=False,
        )

    # Composite index for the CID matching lookup:
    # WHERE group_job_id = :gid AND normalized_cid = :cid
    if not _has_index(
        "target_group_history_rows",
        "idx_tg_history_rows_job_cid",
    ):
        op.create_index(
            "idx_tg_history_rows_job_cid",
            "target_group_history_rows",
            ["group_job_id", "normalized_cid"],
            unique=False,
        )

    # Composite index for full-name fallback matching:
    # WHERE group_job_id = :gid AND normalized_full_name = :name
    if not _has_index(
        "target_group_history_rows",
        "idx_tg_history_rows_job_name",
    ):
        op.create_index(
            "idx_tg_history_rows_job_name",
            "target_group_history_rows",
            ["group_job_id", "normalized_full_name"],
            unique=False,
        )


def downgrade() -> None:
    for index_name in (
        "idx_tg_history_rows_job_name",
        "idx_tg_history_rows_job_cid",
        "idx_tg_history_rows_job_service_key",
    ):
        if _has_index("target_group_history_rows", index_name):
            op.drop_index(index_name, table_name="target_group_history_rows")
