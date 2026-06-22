# SeamlessFordMIS Desktop SQLite Feasibility Audit

วันที่ตรวจ: 2026-05-27

ขอบเขต: audit และ roadmap สำหรับ Desktop Local Edition เท่านั้น ยังไม่ implement SQLite runtime และไม่เปลี่ยน business logic เดิม

## 1. Executive Summary

Desktop Local Edition ทำได้ แต่ไม่ควรใช้วิธีเปลี่ยน `DATABASE_URL` เป็น SQLite แล้วรันระบบเดิมทันที เพราะ backend ปัจจุบันผูกกับ PostgreSQL หลายชั้น:

- SQLAlchemy models ใช้ `sqlalchemy.dialects.postgresql.UUID` และ `JSONB` โดยตรง
- Alembic migrations ใช้ `CREATE EXTENSION pgcrypto`, `gen_random_uuid()`, `postgresql_where`, `pg_indexes`, และ JSONB casts
- Services บางส่วนใช้ PostgreSQL upsert ผ่าน `sqlalchemy.dialects.postgresql.insert`
- Phase F population service ใช้ raw SQL พร้อม `ON CONFLICT`, `now()`, และ schema assumptions ของ PostgreSQL

ข้อสรุป: ทำได้แบบ phased refactor โดยเริ่มจาก portable DB type/config layer และ SQLite schema strategy แยกจาก LAN/PostgreSQL edition. ห้าม rewrite matching/result/import logic ในรอบแรก ให้ reuse services เดิมและเพิ่ม database compatibility wrapper รอบ storage/persistence แทน

Risk ต่อ business rules สูงถ้าเปลี่ยน schema/queries โดยไม่มี regression tests โดยเฉพาะ:

- exact CID priority
- invalid identifier ไม่ถูกนับเป็น no-history
- multi-sheet target group history
- visible result table 1 คน = 1 แถว
- provenance/source history
- export ที่ต้องสะท้อน result จริง

คำแนะนำ phase ถัดไป: Phase D2 ควรทำ prototype backend boot ด้วย SQLite แบบ read/write smoke ก่อน โดยยังไม่เปิดใช้เป็น production และต้องมี regression tests ครอบ business rules หลัก

## 2. Database Model Audit

ภาพรวม models: ตารางส่วนใหญ่ใช้ basic SQLAlchemy types ที่ SQLite รองรับได้ เช่น `Text`, `String`, `Integer`, `BigInteger`, `Date`, `DateTime`, `Boolean`, `Numeric`, `ForeignKey`, `Index`. จุดไม่ portable คือ UUID/JSONB/partial index/server default

| model/table | current type/feature | SQLite compatible? | action needed | risk |
|---|---|---|---|---|
| `UUIDPrimaryKeyMixin` / all UUID tables | `PGUUID(as_uuid=True)`, `server_default=text("gen_random_uuid()")` | No direct | สร้าง portable GUID type เช่น string UUID หรือ SQLAlchemy `TypeDecorator`; generate UUID ฝั่ง Python | High: PK/FK ทุกตารางกระทบ |
| `TimestampMixin` | `DateTime(timezone=True)`, `server_default=func.now()` | Partial | ใช้ Python-side default/update หรือ SQLite-safe `CURRENT_TIMESTAMP`; normalize timezone | Medium: audit timestamps |
| `patients` | partial unique indexes `postgresql_where=pid IS NOT NULL`, `citizen_id IS NOT NULL` | Partial | ใช้ SQLite partial index ถ้า version รองรับ หรือ enforce uniqueness app-side; migration แยก | High: duplicate identity handling |
| `audit_logs` | `JSONB` old/new values | No direct | ใช้ portable JSON type หรือ serialized `Text` | Medium: audit trail must persist |
| `staging_history_records` | `JSONB raw_json`, UUID FKs | No direct | portable JSON + UUID strategy | High: provenance/import audit |
| `target_group_rows` | `JSONB raw_json`, `normalized_target_history_service_keys`, UUID FKs | No direct | portable JSON/list storage | High: target-group-side history and provenance |
| `target_group_history_rows` | `JSONB raw_json`, UUID FKs, sheet/file provenance | No direct | portable JSON + UUID strategy; keep sheet/file IDs | High: multi-sheet history evidence |
| `target_group_results` | `JSONB matched_service_keys`, `selected_service_keys`, UUID FKs, Boolean/defaults, Numeric | Partial | portable JSON; verify Decimal/Numeric precision; Python defaults | High: visible result + latest date correctness |
| `target_group_result_summaries` | `JSONB selected_service_keys`, unique-ish summary index, PostgreSQL upsert used by service | Partial | portable JSON; DB-specific upsert abstraction | High: cached summary/export stale behavior |
| `target_group_sheets` | `JSONB column_names_json`, UUID FKs | No direct | portable JSON; retain sheet metadata | High: every-sheet evidence |
| `source_files` / `target_group_job_files` | UUID FKs, file path text, DateTime | Partial | portable UUID; path strategy update | Medium: source provenance/download |
| `import_jobs` / `target_group_jobs` | UUID mixin, counters/defaults, hashes | Partial | portable UUID/defaults | Medium: workflow state |
| `disease_screening_records` | UUID FKs, composite indexes | Partial | portable UUID; indexes mostly OK | High: service/date history lookup |
| `diagnosis_history` | UUID FKs, date/service indexes | Partial | portable UUID | Medium: older history path if still used |
| `disease_mapping` | Boolean default, text indexes | Mostly | verify boolean default in SQLite | Low |

Model-level blocker: imports like `from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID` are spread across model files. SQLite mode needs either:

1. a compatibility module, e.g. `app.db.types.Guid`, `app.db.types.JSONType`, then update models once; or
2. separate model metadata for desktop, which is riskier and more duplicated

Recommended approach: one portable model layer with custom types and backend-specific migration paths.

## 3. Alembic Migration Audit

Current PostgreSQL migrations should not be run against SQLite unchanged.

| migration | purpose | SQLite compatible? | action needed | notes |
|---|---|---|---|---|
| `20260407_0001_initial_schema.py` | initial schema | No | rewrite for SQLite | Uses `CREATE EXTENSION pgcrypto`, `postgresql.UUID`, `gen_random_uuid()`, `JSONB`, `postgresql_where`, `now()` |
| `20260417_0002_multi_file_pdf_support.py` | source files + multi-file metadata | No | rewrite | UUID/JSONB/server defaults |
| `20260417_0003_phase1_identifier_mapping.py` | identifier mapping columns | Mostly | portable migration possible | add/drop columns only; check SQLite alter limitations |
| `20260417_0004_phase2_disease_screening_pipeline.py` | disease screening records | No | rewrite | UUID, `gen_random_uuid()`, composite indexes, alter column defaults |
| `20260417_0005_phase3_target_group_pipeline.py` | target group counters/validation | Partial | rewrite default removals | SQLite has limited `ALTER COLUMN` support |
| `20260420_0006_phase5_result_generation.py` | result generation fields | No | rewrite | UUID, JSONB, `selected_service_keys = '[]'::jsonb`, boolean SQL |
| `20260420_0007_phase5_result_generation_compat.py` | nullable disease key compatibility | Partial | batch migration if needed | SQLite alter nullable needs batch pattern |
| `20260420_0008_phase10_state_matching_overdue.py` | target-group-side history fields | No | rewrite | JSONB and indexes; important business evidence |
| `20260422_0009_target_group_multi_sheet_metadata.py` | sheet metadata/history rows | No | rewrite | UUID/JSONB and multiple schema changes |
| `20260503_0010_composite_history_index.py` | performance indexes | Mostly | verify index names/columns | likely portable if columns exist |
| `20260503_0011_phase_d_person_link_fields.py` | person link/review fields | Partial | rewrite defaults with SQLite-safe syntax | boolean server default and alter/drop behavior |
| `20260504_0012_phase_e_result_summary_cache.py` | summary cache | No | rewrite | uses `pg_indexes`, UUID, JSONB, `gen_random_uuid()` |
| `20260504_0013_phase_e_perf_indexes_linked_scaffold.py` | person master/identifiers/events scaffold | No | rewrite | uses `pg_indexes`, UUID, server defaults |
| `20260506_0014_phase_f_unique_constraints.py` | unique indexes for Phase F upsert | No | rewrite | checks `pg_indexes`; upsert constraints matter |
| `20260508_0015_add_source_set_hash_to_result_summary.py` | source set hash in summaries | Mostly | portable add column possible | easy once base schema exists |

Migration recommendation:

- Prototype only: allow `Base.metadata.create_all()` with portable model types against an empty SQLite DB
- Production Desktop: create versioned SQLite migration path, either `alembic/versions_desktop/` or a separate SQLite Alembic branch with explicit `render_as_batch=True`
- Do not point existing PostgreSQL Alembic chain at SQLite

## 4. Query Compatibility Audit

| file | query/function | issue | SQLite-safe alternative |
|---|---|---|---|
| `backend/app/services/result_generation_service.py` | `from sqlalchemy.dialects.postgresql import insert as pg_insert` | PostgreSQL-only upsert for summary cache | add dialect-aware upsert helper; SQLite uses `sqlite_insert(...).on_conflict_do_update()` |
| `backend/app/services/result_generation_service.py` | `.ilike(...)` result search | SQLAlchemy compiles SQLite `ilike` to lower/LIKE, usually OK but must test Thai/case behavior | use portable search helper; index expectations differ |
| `backend/app/services/result_generation_service.py` | `text("now()")` in upsert update values | PostgreSQL function | use Python datetime or SQLAlchemy `func.current_timestamp()` |
| `backend/app/services/phase_f_population_service.py` | `from sqlalchemy.dialects.postgresql import insert as pg_insert` | PostgreSQL-specific import | remove/abstract if used in Desktop |
| `backend/app/services/phase_f_population_service.py` | raw SQL `INSERT ... ON CONFLICT DO NOTHING` | SQLite supports newer `ON CONFLICT`, but syntax/UUID/time behavior must be tested | use dialect-aware SQLAlchemy insert helpers or SQLite-specific branch |
| `backend/app/services/phase_f_population_service.py` | raw SQL `updated_at = now()` | PostgreSQL-only | Python datetime or SQLite `CURRENT_TIMESTAMP` |
| `backend/app/services/phase_f_population_service.py` | raw SQL against `person_master`, `person_identifiers`, events tables | These tables are migration-created and not represented in current model list from `backend/app/models` | include in desktop schema or disable Phase F until schema exists |
| `backend/app/services/patient_query_service.py` | `.ilike(...)` patient search | likely compiles, but performance/collation differs | test with Thai names and CID/HN; consider normalized search columns |
| `backend/alembic/versions/*.py` | `pg_indexes` checks | PostgreSQL-only introspection | Alembic inspector or SQLite `PRAGMA index_list` in desktop migration |
| `backend/alembic/versions/*.py` | `'[]'::jsonb` | PostgreSQL cast | JSON text `'[]'` or SQLAlchemy JSON default |
| `backend/alembic/versions/*.py` | `postgresql_where` | PostgreSQL-specific keyword | `sqlite_where` in SQLite branch or app-side guard |

No `ARRAY` usage was found in the audited search. JSON usage is JSONB-centric and is a main blocker.

## 5. File Path Audit

Current path sources:

- `.env.example`: `SOURCE_DATA_DIR=../data`, `UPLOAD_DIR=../uploads/target_groups`, `PARSED_CACHE_DIR=../uploads/parsed_cache`, `REPORTS_DIR=../backend/reports`, `BACKUP_DIR=../data/backups`
- `.env.offline.example`: Docker paths `/app/data`, `/app/uploads/...`, `/app/reports`, `/app/logs`, `/backups`
- `docker-compose.yml`: mounts Docker volumes to `/app/data`, `/app/uploads`, `/app/reports`, `/app/logs`
- `backend/app/config.py`: currently has `source_data_dir`, `upload_dir`, `parsed_cache_dir`, `logs_dir`; `reports_dir` and `backup_dir` envs are in examples but not currently modeled in `Settings`
- `backend/app/api/screening_database.py`: stores staged uploads in `settings.source_data_dir`
- `backend/app/services/export_service.py`: exports to `settings.source_data_dir / "exports"`
- Services show user-facing messages mentioning `data/`

Desktop local path strategy:

```text
data/seamlessfordmis.db
data/uploads
data/source_files
data/reports
data/exports
data/backups
logs
config/settings.json
```

Recommended Windows default:

```text
%LOCALAPPDATA%\SeamlessFordMIS\
```

or IT-visible mode:

```text
C:\SeamlessFordMISLocal\
```

Rules:

- Program install folder and patient data folder must be separate
- Uninstall must preserve `data`, `logs`, and backups by default
- Source file paths must remain available for provenance and safe downloads
- If user changes data folder, do it before first import or require explicit migration

## 6. Runtime Mode Design

Add explicit runtime mode without breaking LAN/Docker:

```env
APP_EDITION=desktop_local | lan_server
DATABASE_ENGINE=sqlite | postgres
DATABASE_URL=sqlite:///data/seamlessfordmis.db
DATA_DIR=./data
UPLOAD_DIR=./data/uploads
SOURCE_DATA_DIR=./data/source_files
REPORTS_DIR=./data/reports
BACKUP_DIR=./data/backups
LOGS_DIR=./logs
```

LAN/Docker keeps current values:

```env
APP_EDITION=lan_server
DATABASE_ENGINE=postgres
DATABASE_URL=postgresql+psycopg://...
SOURCE_DATA_DIR=/app/data
UPLOAD_DIR=/app/uploads/target_groups
REPORTS_DIR=/app/reports
BACKUP_DIR=/backups
```

Backend changes for D2:

- `config.py`: add `app_edition`, `database_engine`, `data_dir`, `reports_dir`, `backup_dir`
- `db/session.py`: choose engine options by database engine
  - SQLite: `connect_args={"check_same_thread": False}`, possible `StaticPool` only for tests, WAL pragma on connect
  - PostgreSQL: keep current `pool_pre_ping=True`
- `init_db.py`: prototype may call create_all only for SQLite dev; production should use versioned migration

## 7. SQLite Schema Strategy

### Option A: `create_all()` prototype only

Pros:

- Fastest way to validate backend boot and basic API smoke
- Useful for D2 proof of concept

Cons:

- No controlled upgrade path
- Does not exercise migration history
- Dangerous if presented as production

Use only for prototype.

### Option B: Versioned SQLite migrations

Pros:

- Real upgrade story
- Easier to test clean install/reinstall
- Better for hospital data safety

Cons:

- Requires rewriting migrations or creating a new branch
- Needs migration QA

Recommended for Desktop production.

### Option C: `alembic/versions_desktop`

Pros:

- Keeps PostgreSQL chain intact
- Desktop schema can be SQLite-safe from day one

Cons:

- Two migration paths must stay aligned
- Requires discipline in future schema changes

Recommended if Desktop becomes a real edition.

## 8. Desktop Backend Boot Strategy

Desktop backend should:

- bind `127.0.0.1` only
- use dynamic local port by default, or fixed high port with collision handling
- write selected port to runtime config for frontend shell
- expose local health endpoint `/health` or `/api/health`
- write logs to local `logs/`
- handle clean shutdown from desktop shell
- avoid network exposure unless user explicitly switches to LAN Server Edition
- not auto-run destructive migrations silently

Suggested dev command:

```bat
set APP_EDITION=desktop_local
set DATABASE_ENGINE=sqlite
set DATABASE_URL=sqlite:///data/seamlessfordmis.db
python -m uvicorn app.main:app --host 127.0.0.1 --port 0
```

For packaged app, the shell should choose a port and pass it explicitly.

## 9. Frontend Strategy

Current `frontend/src/lib/api.ts`:

```ts
const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8010";
```

This is workable for dev but not ideal for desktop packaging because the port may be dynamic and build-time env is not enough.

Options:

| option | approach | pros | cons |
|---|---|---|---|
| Backend serves static frontend | build frontend static/assets and serve from FastAPI | same-origin `/api`, no dynamic API injection | Next.js server features must be checked |
| Desktop shell injects runtime API base | WebView loads local frontend and injects config | supports dynamic port | needs shell integration |
| Keep Next.js local server | shell starts backend + Next server | maximum frontend reuse | heavier packaging, Node runtime burden |

Recommendation for prototype:

- use browser/WebView pointing to local frontend dev/prod server only for D3 proof
- for production desktop, prefer backend-served built frontend or WebView2/Tauri asset bundle with runtime API base injection
- do not hardcode `localhost:8010`

## 10. Backup / Restore Strategy

Desktop backup output:

```text
data/backups/YYYYMMDD-HHMMSS-seamlessfordmis-desktop-backup.zip
```

Contents:

```text
data/seamlessfordmis.db
data/source_files/
data/uploads/
data/reports/
data/exports/        optional
config/settings.json
backup_manifest.json
```

Manifest:

```json
{
  "app_edition": "desktop_local",
  "app_version": "...",
  "schema_version": "...",
  "created_at": "...",
  "database_engine": "sqlite",
  "contains_patient_data": true
}
```

Restore rules:

- must require typed confirmation such as `RESTORE`
- warn that backup contains personal/patient data
- stop local backend writes before replacing DB
- validate manifest before restore
- restore only from user-selected backup path
- never restore silently

Uninstall:

- remove app binaries only
- preserve data folder by default
- delete-all-data must be separate advanced tool with typed confirmation:

```text
DELETE ALL PATIENT DATA
```

## 11. Testing Impact

Required regression tests before claiming Desktop readiness:

| test | purpose |
|---|---|
| exact CID match | preserve highest-priority identifier rule |
| invalid CID not no-history | invalid identifier must not be silently counted as no-history |
| multi-sheet target group | every file/every sheet read |
| target-group-side history evidence | sheet-side history remains valid evidence |
| latest date selected service only | no cross-service contamination |
| visible result 1 person = 1 row | provenance must not duplicate visible rows |
| provenance completeness | source file/sheet/row visible in detail |
| ambiguous identity review_required | no guessing missing identity |
| export result accuracy | Excel/CSV mirrors generated result |
| backup/restore | DB + files + manifest restored |
| app restart persistence | SQLite DB survives close/reopen |
| clean machine no Docker | packaged app does not need Docker/Postgres/Python/Node |

Use non-sensitive sample data only.

## 12. Recommended Desktop Architecture

Phase D2 prototype:

```text
Python launcher
  -> starts FastAPI on 127.0.0.1:<port>
  -> SQLite local DB
  -> local data folder
  -> opens browser/WebView to frontend
```

Production candidates:

| technology | resource usage | build complexity | Windows compatibility | reuse | risk |
|---|---|---|---|---|---|
| Python + FastAPI + Browser/WebView | Low/medium | Low | Good | Backend reuse high, frontend reuse medium | UI shell less native |
| Tauri + local FastAPI/SQLite | Low | Medium/high | Good | Frontend reuse high | Rust/Tauri packaging complexity |
| .NET WebView2 + local FastAPI/SQLite | Medium | Medium | Very good on Windows | Frontend reuse high | Need .NET build/signing pipeline |
| Electron | High | Medium | Good | Frontend reuse high | Larger package/resource use |

Recommendation:

- Prototype with Python + FastAPI + SQLite + browser/WebView launcher
- Evaluate .NET WebView2 or Tauri only after D2/D4 prove business workflow on SQLite
- Avoid Electron unless the team needs it for packaging speed and accepts size overhead

## 13. Phase D2 Plan: Local Data Layer Prototype

Goal: backend boots with SQLite without Docker and without breaking PostgreSQL/Docker edition.

Expected deliverables:

- `DATABASE_ENGINE=sqlite`
- SQLite engine/session config
- local path config
- local health endpoint works
- basic API smoke works
- PostgreSQL/Docker edition still works

Proposed implementation order:

1. Add DB compatibility types: GUID and JSON
2. Replace direct model imports of `PGUUID`/`JSONB` with compatibility types
3. Add settings for `APP_EDITION`, `DATABASE_ENGINE`, `DATA_DIR`, `REPORTS_DIR`, `BACKUP_DIR`
4. Add SQLite engine branch and PRAGMA setup
5. Prototype schema creation with `create_all()` for an empty local DB only
6. Run `/health`, `/api/system/status`, `/api/screening-database/imports?limit=1`
7. Add smoke tests for both postgres URL config and sqlite URL config

Do not implement D2 until this D1 audit is reviewed.

## 14. Phase D3 Plan: Desktop Shell Prototype

Prototype candidate: Python launcher first.

Responsibilities:

- choose/prepare data directory
- start FastAPI on `127.0.0.1`
- wait for `/health`
- open browser/WebView
- stream/scrub local logs
- stop backend on exit
- show data folder and backup status

Future shell candidates:

- Tauri if frontend bundling and native shell quality matter
- .NET WebView2 if Windows installer/native integration is the priority
- Electron only if development speed outweighs package size

## 15. Phase D4 Plan: Desktop Workflow Validation

Use non-sensitive sample data.

Checklist:

1. First launch creates local database
2. Import screening database
3. Import target group multi-sheet Excel
4. Generate result
5. Review visible result table
6. Open detail/source history
7. Edit/follow-up note if current feature supports it
8. Export Excel
9. Backup
10. Restore
11. Close app / reopen app
12. Confirm data remains

Do not claim Desktop readiness until this is tested on a clean machine.

## 16. Phase D5 Packaging Strategy

Installer target:

```text
SeamlessFordMIS-Desktop-Setup.exe
```

Installed app:

```text
SeamlessFordMIS Desktop.exe
```

Installer responsibilities:

- install app binaries
- create desktop shortcut
- create start menu shortcut
- create data folder if missing
- preserve data on uninstall
- never remove SQLite DB/uploads/source_files/backups/logs by default
- ship no real `.env`, DB, patient files, backups, or uploaded files
- advanced delete-all-data tool requires typed confirmation:

```text
DELETE ALL PATIENT DATA
```

## 17. Phase D6 Data Safety / Privacy Rules

Minimum privacy:

- local-only by default
- API binds `127.0.0.1` only
- no telemetry
- no cloud sync
- no auto-upload logs
- logs must not include secrets
- backup/export warning every time
- do not claim encryption until actually implemented and verified

Optional future:

- encrypted backup zip
- SQLCipher
- app password
- role-based access for LAN edition only

## 18. Recommendation

Decision: **ทำได้ แต่ต้อง refactor database compatibility layer ก่อน และต้องแยก migration strategy สำหรับ SQLite**

Immediate next step:

1. Review this D1 audit
2. Approve D2 scope: SQLite prototype only, no business logic changes
3. Add regression tests around business rules before or alongside D2
4. Build minimal SQLite backend boot proof

Do not:

- run PostgreSQL Alembic migrations directly against SQLite
- rewrite matching/result/import logic
- remove Docker/LAN edition
- claim Desktop production-ready before clean machine test
