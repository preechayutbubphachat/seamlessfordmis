# Desktop SQLite D2 Prototype Notes

Date: 2026-05-27

Scope: Phase D2 Local Data Layer Prototype. This phase adds the minimum backend runtime/data layer needed to boot with SQLite for Desktop Local Edition. It does not implement the desktop shell, production SQLite migrations, or full business workflow validation.

## 1. Implemented

- Added runtime edition/database settings:
  - `APP_EDITION=desktop_local | lan_server`
  - `DATABASE_ENGINE=sqlite | postgres`
  - `DATABASE_URL=sqlite:///data/seamlessfordmis.db`
  - `DATA_DIR`, `SOURCE_DATA_DIR`, `UPLOAD_DIR`, `PARSED_CACHE_DIR`, `REPORTS_DIR`, `EXPORTS_DIR`, `BACKUP_DIR`, `LOG_DIR` / `LOGS_DIR`
- Added SQLite-aware engine creation with:
  - `check_same_thread=False`
  - `PRAGMA foreign_keys=ON`
  - `PRAGMA journal_mode=WAL`
  - `PRAGMA synchronous=NORMAL`
- Added portable model types:
  - `GUID`: PostgreSQL native UUID, SQLite `CHAR(36)`
  - `JSONType`: PostgreSQL JSONB, SQLite JSON
- Replaced direct model imports of PostgreSQL `UUID`/`JSONB` with the compatibility types.
- Added Desktop path initializer:
  - `python -m app.desktop.init_paths`
  - CLI output is forced to UTF-8 so Windows machines with Thai paths do not fail on console encoding.
- Added Desktop SQLite schema bootstrap prototype:
  - `python -m app.desktop.init_db`
  - Uses `Base.metadata.create_all()` only for the D2 prototype.
  - Adds `desktop_schema_metadata` with `schema_strategy=create_all_prototype`.
- `/health` now returns safe runtime metadata:
  - `status`
  - `app_edition`
  - `database_engine`

## 2. Prototype Boundaries

This is not the production Desktop database migration path.

Allowed in D2:

- initialize an empty local SQLite database
- boot FastAPI locally
- verify `/health`
- prepare compatibility seams for future query work

Not claimed in D2:

- full import workflow on SQLite
- full target group matching/result generation on SQLite
- production upgrade/migration story
- desktop executable packaging
- clean machine validation

## 3. Files Changed

| File | Change |
|---|---|
| `backend/app/config.py` | Added edition/database/path settings and helper properties |
| `backend/app/db/session.py` | Added SQLite engine path handling and PRAGMA setup |
| `backend/app/db/types.py` | Added portable `GUID` and `JSONType` types |
| `backend/app/db/compat.py` | Added initial dialect/query compatibility helpers |
| `backend/app/db/init_db.py` | Added Desktop path init and prototype schema metadata for SQLite mode |
| `backend/app/desktop/__init__.py` | Added Desktop helper package |
| `backend/app/desktop/paths.py` | Added local folder initializer and `settings.json` writer |
| `backend/app/desktop/init_paths.py` | Added CLI entrypoint for path initialization |
| `backend/app/desktop/init_db.py` | Added CLI entrypoint for SQLite schema bootstrap |
| `backend/app/models/*.py` | Replaced direct PostgreSQL UUID/JSONB model types with compatibility types |
| `backend/app/main.py` | Added safe runtime metadata to `/health` |
| `.env.example` | Added Desktop Local prototype variables |
| `.env.offline.example` | Added explicit LAN/Postgres runtime variables |
| `docker-compose.yml` | Passed explicit LAN/Postgres runtime variables to backend |
| `docs/DESKTOP_SQLITE_D2_NOTES.md` | Added this implementation note |

## 4. PostgreSQL Compatibility Still Remaining

| Area | Status | D3/D4 action |
|---|---|---|
| Alembic migrations | PostgreSQL chain remains PostgreSQL-specific | Create SQLite migration branch or desktop migration command |
| `result_generation_service.py` summary upsert | Still uses PostgreSQL `pg_insert` | Add dialect-aware upsert without changing summary semantics |
| `phase_f_population_service.py` raw SQL | Still assumes PostgreSQL-style linked scaffold tables | Decide whether to port Phase F tables to SQLite or defer behind feature guard |
| `.ilike()` search | Likely compiles on SQLite, but collation/performance must be tested | Add query helper tests for CID/HN/name search |
| PostgreSQL partial indexes | Model still carries `postgresql_where`; SQLite create_all ignores it | Add SQLite-specific migration/index strategy |
| JSON filtering/search | JSON storage now portable, but JSON query behavior not validated | Add SQLite JSON behavior tests before workflow validation |

## 5. SQLite Limitations

- SQLite is appropriate for single-user local Desktop mode, not multi-user LAN concurrency.
- WAL mode improves local durability/concurrency but does not make SQLite a server database.
- SQLite date/time and timezone behavior differs from PostgreSQL; business date rules need regression tests.
- SQLite JSON type stores JSON text and behavior differs from PostgreSQL JSONB indexing/operators.
- `create_all()` has no upgrade semantics. It is not enough for production hospital data.

## 6. Local Backend Commands

Windows PowerShell:

```powershell
cd backend
$env:APP_EDITION = "desktop_local"
$env:DATABASE_ENGINE = "sqlite"
$env:DATABASE_URL = "sqlite:///data/seamlessfordmis.db"
$env:DATA_DIR = "./data"
$env:SOURCE_DATA_DIR = "./data/source_files"
$env:UPLOAD_DIR = "./data/uploads"
$env:PARSED_CACHE_DIR = "./data/parsed_cache"
$env:REPORTS_DIR = "./data/reports"
$env:EXPORTS_DIR = "./data/exports"
$env:BACKUP_DIR = "./data/backups"
$env:LOG_DIR = "./logs"
python -m app.desktop.init_db
python -m uvicorn app.main:app --host 127.0.0.1 --port 8010
```

Windows Command Prompt:

```bat
cd backend
set APP_EDITION=desktop_local
set DATABASE_ENGINE=sqlite
set DATABASE_URL=sqlite:///data/seamlessfordmis.db
set DATA_DIR=./data
set SOURCE_DATA_DIR=./data/source_files
set UPLOAD_DIR=./data/uploads
set PARSED_CACHE_DIR=./data/parsed_cache
set REPORTS_DIR=./data/reports
set EXPORTS_DIR=./data/exports
set BACKUP_DIR=./data/backups
set LOG_DIR=./logs
python -m app.desktop.init_db
python -m uvicorn app.main:app --host 127.0.0.1 --port 8010
```

Linux/macOS:

```bash
cd backend
APP_EDITION=desktop_local \
DATABASE_ENGINE=sqlite \
DATABASE_URL=sqlite:///data/seamlessfordmis.db \
DATA_DIR=./data \
SOURCE_DATA_DIR=./data/source_files \
UPLOAD_DIR=./data/uploads \
PARSED_CACHE_DIR=./data/parsed_cache \
REPORTS_DIR=./data/reports \
EXPORTS_DIR=./data/exports \
BACKUP_DIR=./data/backups \
LOG_DIR=./logs \
python -m app.desktop.init_db

APP_EDITION=desktop_local \
DATABASE_ENGINE=sqlite \
DATABASE_URL=sqlite:///data/seamlessfordmis.db \
python -m uvicorn app.main:app --host 127.0.0.1 --port 8010
```

Health smoke:

```bash
curl http://127.0.0.1:8010/health
```

Expected shape:

```json
{"status":"ok","app_edition":"desktop_local","database_engine":"sqlite"}
```

## 7. Known Business Rule Risks

Regression tests are required before claiming workflow readiness:

- exact CID priority
- invalid identifier must not silently become no-history
- target group file reads every file and every sheet
- target-group-file-side history remains valid evidence
- latest date comes only from selected services
- visible result table remains 1 person = 1 row
- provenance is complete but does not duplicate visible rows
- ambiguous identity remains `review_required` / `needs_review`
- export reflects real generated results
- restart preserves SQLite data

## 8. D3 Recommendation

Next phase should not jump straight to packaging. Recommended D3 sequence:

1. Add regression tests around the business rules above.
2. Add dialect-aware upsert/search helpers and port only the minimal queries needed for target-group result smoke.
3. Validate import -> target group -> generate result -> export with non-sensitive sample data on SQLite.
4. Only after backend workflow smoke is stable, build a Desktop shell prototype.

Desktop shell candidates:

- Prototype: Python + FastAPI + pywebview or browser launcher
- Production candidate: Tauri or .NET WebView2 if a more native Windows installer/shell is needed

## 9. Data Safety Rules

- Desktop backend binds `127.0.0.1` only in local commands.
- No telemetry or cloud sync is added.
- No auto-upload logs are added.
- No encryption claim is made.
- Backup/export must warn that files may contain patient data.
- Uninstall must preserve local data by default.
