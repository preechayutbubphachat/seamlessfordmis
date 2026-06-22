# Legacy DB Migration Strategy

## Problem

The production-like database named `seamlessfordmis` is not on the same schema lineage as the active `backend/alembic` migration chain.

Observed issues:

- the database has no `alembic_version` table
- table names overlap with the current application model
- table structures differ materially from the current ORM models
- running `backend/alembic upgrade head` directly against the legacy database fails early with duplicate-table errors

This means the current database must not be migrated by guesswork, forced stamping, or direct upgrade-from-zero.

## Current Safe Conclusion

Treat the existing `seamlessfordmis` database as a legacy source database, not as an in-place migration target yet.

For current development and verification:

- use a fresh database for the current application schema
- run `backend/alembic` only against that fresh database
- verify imports and result generation there first

## Recommended Migration Path

### Phase A: Assess and freeze

1. Back up the legacy database completely.
2. Export schema metadata from the legacy database.
3. Document table-by-table differences against the current ORM.
4. Identify which legacy tables are still operationally needed.

### Phase B: Build a controlled target database

1. Create a fresh database for the current application schema.
2. Run `backend/alembic upgrade head` against that new database.
3. Seed essential reference data such as `disease_mapping`.

### Phase C: Map legacy data to current models

Create explicit migration scripts for each logical area:

- disease screening import history
- patient/person identity
- target group jobs
- target group rows
- target group results, only if reuse is truly needed
- audit logs, only if they are needed operationally

Every mapping must be explicit.
Do not rely on column-name similarity alone.

### Phase D: Dry run and reconcile

1. Run migration scripts into a staging database.
2. Compare row counts and representative records.
3. Check identifier normalization outcomes.
4. Check whether provenance can still be traced.
5. Review a sample of result-generation outputs against known source files.

### Phase E: Cutover

1. Schedule a cutover window.
2. Take a fresh backup.
3. Re-run the approved migration scripts.
4. Switch application configuration to the new database.
5. Keep the legacy database read-only for rollback and audit review.

## What Not To Do

- do not `stamp head` on the legacy database without table-by-table validation
- do not run `upgrade head` directly on the legacy database
- do not drop legacy tables in place just to make migrations pass
- do not assume old `target_group_rows` and current `TargetGroupRow` are compatible

## Minimal Practical Next Step

Before any production cutover work, create an inspection script or checklist that captures:

- legacy table names
- legacy column names
- current ORM table names
- current ORM critical fields
- compatibility status per table:
  - compatible
  - partially compatible
  - incompatible
  - no longer used

This gives a safe foundation for writing one-way migration scripts.

## Supporting Documents

- [Legacy schema gap report](C:/2025/web-69/โรงบาลหนองพอก/seamlessfordmis/docs/legacy-schema-gap-report.md)
- [Legacy migration mapping](C:/2025/web-69/โรงบาลหนองพอก/seamlessfordmis/docs/legacy-migration-mapping.md)
- [Legacy migration runbook](C:/2025/web-69/โรงบาลหนองพอก/seamlessfordmis/docs/legacy-migration-runbook.md)

## Verified Reality From Current Investigation

- `backend/alembic` works on a fresh database
- the legacy `seamlessfordmis` database is schema-incompatible with the current migration chain
- multi-sheet target-group import and target-group-side history logic were verified successfully in a fresh verification database
