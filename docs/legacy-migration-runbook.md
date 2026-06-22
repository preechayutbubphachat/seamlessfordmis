# Legacy Migration Runbook

## Goal

Move data from the legacy `seamlessfordmis` database into a fresh current-schema database without mutating the legacy source.

## Safety Rules

- legacy database is read-only during migration
- target database is disposable until validation passes
- no in-place Alembic upgrade on legacy database
- no forced Alembic stamp on legacy database
- regenerate result snapshots after migration unless explicitly approved otherwise

## Step 1: Backup

Create a full backup of the legacy database before any work.

```powershell
pg_dump -Fc -h localhost -U postgres -d seamlessfordmis -f backups/seamlessfordmis-before-current-schema-migration.dump
```

## Step 2: Inspect Legacy Schema

```powershell
$env:DATABASE_URL='postgresql+psycopg://postgres:postgres@localhost:5432/seamlessfordmis?connect_timeout=3'
$env:PYTHONPATH='backend'
python backend/scripts/inspect_legacy_db_schema.py
python backend/scripts/compare_legacy_schema_to_models.py
```

Save outputs as migration evidence.

## Step 3: Create Fresh Target DB

```powershell
createdb -h localhost -U postgres seamlessfordmis_current
```

Run current migrations:

```powershell
$env:DATABASE_URL='postgresql+psycopg://postgres:postgres@localhost:5432/seamlessfordmis_current?connect_timeout=3'
python - <<'PY'
from alembic.config import Config
from alembic import command
cfg = Config('alembic.ini')
cfg.set_main_option('script_location', 'backend/alembic')
command.upgrade(cfg, 'head')
PY
```

## Step 4: Seed Reference Data

```powershell
$env:DATABASE_URL='postgresql+psycopg://postgres:postgres@localhost:5432/seamlessfordmis_current?connect_timeout=3'
$env:PYTHONPATH='backend'
python backend/app/seeds/disease_mapping_seed.py
```

## Step 5: Transform Data

Dry-run the core transform first:

```powershell
$env:LEGACY_DATABASE_URL='postgresql://postgres:postgres@localhost:5432/seamlessfordmis?connect_timeout=3'
$env:TARGET_DATABASE_URL='postgresql://postgres:postgres@localhost:5432/seamlessfordmis_current?connect_timeout=3'
$env:PYTHONPATH='backend'
python backend/scripts/migrate_legacy_core_dry_run.py --sample-size 5
```

The dry-run must report:

- `writes_performed = false`
- legacy and target URLs are different
- target schema has the current required tables
- target core tables are empty before any apply script is allowed

The first safe apply script is:

```powershell
$env:LEGACY_DATABASE_URL='postgresql://postgres:postgres@localhost:5432/seamlessfordmis?connect_timeout=3'
$env:TARGET_DATABASE_URL='postgresql://postgres:postgres@localhost:5432/seamlessfordmis_current?connect_timeout=3'
$env:PYTHONPATH='backend'
python backend/scripts/migrate_legacy_core_apply.py --limit 100
```

Important default behavior:

- `migrate_legacy_core_apply.py` opens a transaction and rolls it back by default.
- Pass `--limit` for smoke tests before full runs.
- It refuses to run when legacy and target URLs are the same.
- It refuses to run when target core tables are not empty unless `--allow-non-empty` is explicitly passed.
- It commits only when `--execute` is passed.

Only run a committed apply against a disposable fresh target database after dry-run output is reviewed:

```powershell
python backend/scripts/migrate_legacy_core_apply.py --execute
```

The current apply v1 inserts only:

1. `import_jobs`
2. `patients`
3. `target_group_jobs`
4. `target_group_job_files`
5. `target_group_rows`

Implement remaining one-way scripts in this order:

1. `diagnosis_history`
2. `disease_screening_records`
3. `target_group_sheets`
4. `target_group_history_rows` from original files or explicit raw payload history

Do not migrate `target_group_results` as active final results unless there is a specific audit requirement.
Regenerate results with current business logic instead.

## Step 6: Reconcile

Check:

- row counts per table
- count of valid normalized identifiers
- target group row counts by job
- disease screening record counts by service key
- result generation for one known target group
- sample patient detail modal provenance

## Step 7: Cutover

Only after validation:

1. stop app writes
2. run final one-way migration
3. regenerate required result snapshots
4. point application `DATABASE_URL` to current target DB
5. keep legacy DB read-only for rollback/audit

## Rollback

Rollback is configuration-based:

- point `DATABASE_URL` back to legacy DB only if the legacy-compatible application version is also restored
- do not point the current app code at the legacy DB
