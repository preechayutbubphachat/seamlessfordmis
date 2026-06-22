# Current Phase

## Multi-Sheet Target Group History Verification

Current focus:

- inspect every sheet in uploaded target group workbooks
- classify roster/history/mixed sheets conservatively
- preserve file + sheet + row provenance
- use target-group-side history in result generation
- avoid classifying people as `no_history_found` when valid target-group evidence exists

## Verified In This Round

- multi-sheet import works against a fresh verification database
- `target_group_sheets` metadata is persisted
- target-group history rows are persisted with source provenance
- result generation now counts target-group history even when service evidence exists but visit date is invalid
- person-level output can produce `target_group_file_only` from real uploaded target group files

## Important Operational Note

The legacy database `seamlessfordmis` is not on the same migration lineage as the current `backend/alembic` chain.

Use [docs/legacy-db-migration-strategy.md](C:/2025/web-69/โรงบาลหนองพอก/seamlessfordmis/docs/legacy-db-migration-strategy.md) before attempting in-place migration of that database.
