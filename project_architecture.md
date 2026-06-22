# PROJECT_ARCHITECTURE.md

> เอกสารนี้เป็นแนวทางสถาปัตยกรรมใหม่สำหรับให้ AI / Codex / Claude / developer เดินงานต่อได้ถูกทิศทาง โดยเป้าหมายคือแยกแนวทาง **Desktop Local Edition** ออกจาก Docker/LAN Edition เดิมอย่างปลอดภัย
>
> เป้าหมายใหม่: ทำให้ seamlessfordmis เป็นโปรแกรมที่เปิดจากเครื่องผู้ใช้ได้โดยตรง ไม่ต้องใช้ Docker สำหรับรุ่นเครื่องเดียว ใช้ทรัพยากรน้อยลง และยังคง business rules สำคัญทั้งหมดของระบบคัดกรองกลุ่มเป้าหมาย

---

## 1. Product direction

### 1.1 Current deployment direction

ปัจจุบันระบบมีแนวทาง Offline/LAN ผ่าน Docker Compose แล้ว โดยมี service หลัก:

- PostgreSQL database
- FastAPI backend
- Next.js frontend
- nginx reverse proxy
- Windows Installer
- GUI Launcher
- offline scripts สำหรับ start / stop / backup / restore / migration / healthcheck

แนวทางนี้เหมาะกับหน่วยงานที่มีเครื่องแม่ข่ายหรือ IT ดูแลระบบได้

### 1.2 New target direction

เพิ่มรุ่นใหม่ชื่อ:

```text
SeamlessFordMIS Desktop Local Edition
```

เป้าหมายของรุ่นนี้:

- เปิดเป็นโปรแกรมเดียวจากเครื่องผู้ใช้
- ไม่ต้องติดตั้ง Docker Desktop
- ไม่ต้องติดตั้ง PostgreSQL แยก
- ไม่ต้องติดตั้ง Node.js หรือ Python แยกในเครื่องผู้ใช้ปลายทาง
- ใช้ SQLite เป็น local database
- เก็บไฟล์ทั้งหมดใน local data folder
- ใช้งานได้แบบ offline จริง
- เหมาะกับเครื่องเดียวหรือเจ้าหน้าที่หนึ่งจุดใช้งาน
- ลดความซับซ้อนสำหรับผู้ใช้ทั่วไป

---

## 2. Product editions

### 2.1 Desktop Local Edition — new target

เหมาะกับ:

- ใช้งานคนเดียวหรือเครื่องเดียว
- หน่วยงานขนาดเล็ก
- เจ้าหน้าที่ไม่มีประสบการณ์ด้าน Docker / server
- ต้องการเปิดโปรแกรมเดียวแล้วทำงานทันที
- ต้องการลด resource usage

ลักษณะระบบ:

```text
SeamlessFordMIS Desktop.exe
├─ Desktop UI
├─ App core / local backend
├─ SQLite database
├─ Local file storage
├─ Import / screening / export workflow
└─ Backup / restore tools
```

ผู้ใช้เห็นเพียง:

```text
เปิดโปรแกรม
→ เพิ่มไฟล์ Excel/PDF/CSV
→ นำเข้าข้อมูล
→ จัดการกลุ่มเป้าหมาย
→ คัดกรองผล
→ ดู/แก้ไข/ติดตามผล
→ ส่งออก Excel
→ สำรองข้อมูล
```

### 2.2 LAN Server Edition — keep existing direction

ยังควรเก็บไว้ ไม่ควรลบทิ้ง

เหมาะกับ:

- หลายเครื่องเข้าใช้งานพร้อมกัน
- มีเครื่องแม่ข่าย
- มี IT ดูแล
- ต้องการ PostgreSQL
- ต้องการให้เครื่องอื่นใน LAN เข้าเว็บผ่าน IP

ลักษณะระบบ:

```text
Docker Compose
├─ PostgreSQL
├─ FastAPI backend
├─ Next.js frontend
└─ nginx
```

### 2.3 Decision rule

```text
ใช้เครื่องเดียว / ผู้ใช้ทั่วไป / เครื่องไม่แรง → Desktop Local Edition
หลายเครื่องพร้อมกัน / มี IT / ต้องการ LAN server → LAN Server Edition
```

---

## 3. Non-negotiable business rules

ห้ามเปลี่ยน business rules เหล่านี้ในทุก edition:

1. exact CID / citizen ID 13 หลักสำคัญที่สุด
2. Target group file ต้องอ่านทุกไฟล์ทุก sheet
3. Target-group-file-side history เป็น valid evidence
4. ห้าม ignore ประวัติจาก sheet อื่นของไฟล์กลุ่มเป้าหมาย
5. Latest date ต้องมาจากโรค/บริการที่ผู้ใช้เลือกเท่านั้น
6. Visible result table ต้องเป็น 1 คน = 1 แถว
7. Provenance ต้องเก็บครบ แต่ไม่ทำให้ visible rows ซ้ำ
8. Ambiguous identity ต้อง mark เป็น `review_required` / `needs_review`
9. ห้ามเดาข้อมูลที่หาย
10. ห้ามใช้ fuzzy matching aggressive
11. Invalid identifier ต้องไม่ถูกนับเป็น no-history แบบเงียบ ๆ
12. Non-Thai / insufficient identity ต้องมี category แยก
13. Loading/progress UI ต้องไม่แสดงเปอร์เซ็นต์ปลอม
14. Export ต้องสะท้อนผลลัพธ์ก่อนส่งออกจริง ไม่ใช่ fake save/export

---

## 4. Architecture target: Desktop Local Edition

### 4.1 Recommended architecture

แนะนำให้ทำเป็น desktop shell ที่ครอบ web UI เดิม หรือ UI ที่ reuse logic เดิมให้มากที่สุด

Candidate technology:

```text
Option A: Tauri + local FastAPI/SQLite
Option B: Electron + local FastAPI/SQLite
Option C: Python desktop app + embedded webview + FastAPI/SQLite
Option D: .NET WebView2 launcher + local backend/SQLite
```

Recommendation เบื้องต้น:

```text
Phase prototype: Python + FastAPI + SQLite + WebView/Browser launcher
Production desktop: Tauri หรือ .NET WebView2 ถ้าต้องการ installer ที่ดูเป็น native มากขึ้น
```

เหตุผล:

- Backend เดิมเป็น Python/FastAPI อยู่แล้ว
- Import Excel/PDF logic น่าจะอยู่ใน Python service แล้ว
- ลดการ rewrite business logic
- SQLite ใช้ได้ดีสำหรับ local single-user
- เริ่ม prototype ได้เร็วกว่า rewrite เป็น desktop native ทั้งหมด

### 4.2 Target runtime model

```text
Desktop app process
├─ starts local backend on 127.0.0.1:<dynamic_port>
├─ serves frontend locally or opens embedded webview
├─ stores SQLite db in app data folder
├─ stores uploads/source files/reports/backups in app data folder
└─ stops backend cleanly when app exits
```

### 4.3 Local data folder

Windows suggested path:

```text
%LOCALAPPDATA%\SeamlessFordMIS\
```

หรือถ้าต้องการให้ IT หาเจอง่าย:

```text
C:\SeamlessFordMISLocal\
```

Recommended structure:

```text
SeamlessFordMISLocal\
├─ app\
│  └─ application files
├─ data\
│  ├─ seamlessfordmis.db
│  ├─ uploads\
│  ├─ source_files\
│  ├─ reports\
│  ├─ exports\
│  └─ backups\
├─ logs\
└─ config\
   └─ settings.json
```

### 4.4 SQLite database

Main database file:

```text
data/seamlessfordmis.db
```

SQLite settings to consider:

```sql
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
PRAGMA synchronous=NORMAL;
```

Constraints:

- เหมาะสำหรับ single-user local workflow
- ไม่ควรใช้ SQLite file เดียวให้หลายเครื่องเขียนพร้อมกันผ่าน network share
- ถ้าต้องหลายเครื่องพร้อมกัน ให้ใช้ LAN Server Edition

---

## 5. Migration strategy from PostgreSQL to SQLite support

### 5.1 Goal

ต้องทำให้ backend database layer รองรับทั้ง:

```text
LAN Server Edition: PostgreSQL
Desktop Local Edition: SQLite
```

โดยไม่เปลี่ยน business logic

### 5.2 Required audit

Codex/AI ต้องตรวจ:

- SQLAlchemy models ใช้ type ที่ SQLite รองรับหรือไม่
- Alembic migrations มี PostgreSQL-specific syntax หรือไม่
- Query ใช้ function เฉพาะ PostgreSQL หรือไม่
- JSON/JSONB ใช้อย่างไร
- UUID ใช้แบบ native PostgreSQL หรือ string
- Date/time normalization ทำที่ Python หรือ SQL
- Index/unique constraints ใช้กับ SQLite ได้หรือไม่
- Transaction boundary เหมาะกับ SQLite หรือไม่

### 5.3 Compatibility rules

ควรปรับให้ใช้ portable SQLAlchemy มากที่สุด:

```text
Avoid:
- PostgreSQL-only JSONB operators
- ILIKE without abstraction
- ARRAY type
- UUID native dependency without fallback
- server_default ที่ SQLite ไม่รองรับ
- partial index ที่ SQLite version ปลายทางอาจไม่รองรับ
```

Prefer:

```text
- String UUID
- Text JSON serialized by application if needed
- SQLAlchemy portable expressions
- Python-side normalization
- explicit application validation
```

### 5.4 Migration approach

ไม่ควรเอา Alembic PostgreSQL migrations เดิมไปรัน SQLite ตรง ๆ โดยไม่ตรวจ

แนะนำสร้าง migration path แยก:

```text
backend/app/db/desktop_schema.py
```

หรือทำ Alembic branch ที่รองรับ SQLite ชัดเจน:

```text
alembic/versions_desktop/
```

Phase แรกอาจใช้:

```text
create_all() for prototype only
```

Production ต้องมี:

```text
versioned SQLite schema migration
```

---

## 6. File storage strategy

### 6.1 Principles

- ห้ามเก็บไฟล์ผู้ป่วยใน program install folder ที่ถูกลบตอน uninstall
- ห้ามเก็บไฟล์จริงใน public/static folder
- ต้องแยก source files, uploads, reports, exports, backups ชัดเจน
- ทุกไฟล์นำเข้าต้องมี provenance กลับไปหา source ได้
- Backup ต้องรวม database + source files + uploads + reports + config ที่จำเป็น

### 6.2 Suggested storage paths

```text
data/source_files/     ไฟล์ต้นทาง/import source
 data/uploads/          ไฟล์ที่ upload ผ่าน UI
 data/reports/          report artifacts
 data/exports/          Excel/CSV export output
 data/backups/          backup zip
 logs/                  app logs
 config/settings.json   local settings
```

### 6.3 Backup package

Backup output:

```text
data/backups/YYYYMMDD-HHMMSS-seamlessfordmis-backup.zip
```

Contents:

```text
seamlessfordmis.db
source_files/
uploads/
reports/
exports/ optional
config/settings.json
backup_manifest.json
```

`backup_manifest.json` should include:

```json
{
  "app_version": "...",
  "schema_version": "...",
  "created_at": "...",
  "machine_name": "...",
  "database_file": "seamlessfordmis.db",
  "notes": "Backup contains sensitive patient data"
}
```

---

## 7. Desktop UX target

### 7.1 Main navigation

Desktop Local Edition should feel like one application, not a server stack.

Main screens:

1. Home / Dashboard
2. Import Screening Database
3. Manage Target Groups
4. Result Review & Follow-up Workspace
5. Export / Reports
6. Backup & Restore
7. Settings
8. System Status / Logs

### 7.2 First-run UX

First launch should guide the user:

```text
Welcome
→ Choose data folder
→ Create local database
→ Confirm privacy note
→ Open dashboard
```

### 7.3 Privacy copy

Use careful, non-overpromising wording:

```text
ระบบนี้ประมวลผลข้อมูลในเครื่องนี้เป็นหลัก
โปรดสำรองข้อมูลและเก็บไฟล์ backup อย่างปลอดภัย
ไฟล์ backup/export อาจมีข้อมูลส่วนบุคคลหรือข้อมูลสุขภาพ
```

Avoid:

```text
ปลอดภัย 100%
ไม่มีความเสี่ยง
เข้ารหัสทุกอย่างแล้ว
```

unless encryption is actually implemented and verified.

### 7.4 User workflow

Target workflow:

```text
เปิดโปรแกรม
→ นำเข้าฐานข้อมูลการคัดกรอง
→ เพิ่มไฟล์กลุ่มเป้าหมาย
→ ตรวจ mapping/validation
→ generate result
→ review table
→ เปิดรายละเอียดคน
→ ติดตามผล/แก้ไขข้อมูลประกอบ
→ export Excel
→ backup
```

---

## 8. Backend refactor strategy

### 8.1 Rule

ห้าม rewrite business logic ถ้าไม่จำเป็น

### 8.2 Target structure

แยก backend logic เป็น reusable application core:

```text
backend/app/
├─ core/
├─ services/
│  ├─ import_service.py
│  ├─ target_group_service.py
│  ├─ matching_service.py
│  ├─ result_generation_service.py
│  └─ export_service.py
├─ db/
│  ├─ session.py
│  ├─ models.py
│  ├─ sqlite.py
│  └─ postgres.py
├─ api/
└─ desktop/
   ├─ local_app.py
   ├─ settings.py
   └─ paths.py
```

### 8.3 Configuration

Add explicit runtime mode:

```text
APP_EDITION=desktop_local | lan_server
DATABASE_ENGINE=sqlite | postgres
DATA_DIR=...
```

Desktop default:

```env
APP_EDITION=desktop_local
DATABASE_ENGINE=sqlite
DATABASE_URL=sqlite:///data/seamlessfordmis.db
DATA_DIR=./data
UPLOAD_DIR=./data/uploads
SOURCE_DATA_DIR=./data/source_files
REPORTS_DIR=./data/reports
BACKUP_DIR=./data/backups
```

LAN default:

```env
APP_EDITION=lan_server
DATABASE_ENGINE=postgres
DATABASE_URL=postgresql+psycopg://...
```

---

## 9. Frontend strategy

### 9.1 Reuse existing frontend

ควร reuse UI เดิมให้มากที่สุด เพราะมี workflow/UX หลายส่วนแล้ว

Desktop app can load frontend by:

Option A:

```text
local backend serves built frontend static files
```

Option B:

```text
desktop shell loads local Next.js production server
```

Option C:

```text
Tauri/Electron embeds frontend build
```

### 9.2 API base URL

Desktop should use dynamic local API:

```text
http://127.0.0.1:<local_port>/api
```

Avoid hardcoding:

```text
http://localhost:8010
```

Use runtime injected config or same-origin if frontend is served by backend.

### 9.3 UX differences for Desktop Local Edition

Add local edition UI indicators:

- Badge: `Desktop Local`
- Data folder display
- Backup status
- Last backup date
- SQLite database size
- Warning if database file is on network drive
- Button: Open data folder
- Button: Backup now

---

## 10. Packaging strategy

### 10.1 Desktop installer target

Installer name:

```text
SeamlessFordMIS-Desktop-Setup.exe
```

Installed app:

```text
SeamlessFordMIS Desktop.exe
```

### 10.2 Installer responsibilities

- Install app binaries
- Create Start Menu shortcut
- Create Desktop shortcut
- Create data folder if not exists
- Never delete data folder on uninstall by default
- Register app version
- Optionally create file association for backup files later

### 10.3 Uninstall rule

Default uninstall removes only application files.

Must not remove:

- SQLite database
- uploads
- source files
- exports
- backups
- logs unless explicitly selected

Data deletion must be separate advanced tool with typed confirmation:

```text
DELETE ALL PATIENT DATA
```

---

## 11. Security and privacy requirements

### 11.1 Minimum

- Local-only by default
- API binds to `127.0.0.1` only for single-user Desktop Local Edition
- Do not expose network service unless user explicitly enables LAN mode
- No telemetry
- No auto-upload logs
- No cloud sync
- Backup warning shown every time
- Logs must not include secrets
- Patient data must not be included in crash reports

### 11.2 Optional future encryption

Consider later:

- Encrypted backup zip with password
- Database encryption using SQLCipher or equivalent
- App-level user login
- Role-based access for LAN edition

Do not claim encryption until implemented and verified.

---

## 12. Performance expectations

Desktop Local Edition target:

- Startup under 10–20 seconds on normal office PC
- Import progress shows actual stages, not fake percent
- Large Excel import should be chunked
- UI should remain responsive
- SQLite writes should be transaction-batched
- Indexes must support CID lookup, service/date filtering, result listing

Minimum indexes to verify:

- normalized citizen ID
- group/job ID
- service key
- visit/check date
- person result group key
- provenance result ID

---

## 13. Risk register

| Risk | Impact | Mitigation |
|---|---|---|
| PostgreSQL-specific SQL does not work in SQLite | Desktop prototype fails | Audit queries and migrations first |
| SQLite concurrency limitation | Data corruption/performance issue in multi-user LAN | Desktop Local = single-user only; LAN edition remains PostgreSQL |
| File paths hardcoded for Docker | Import/export fails locally | Centralize path config |
| Business logic accidentally rewritten | Incorrect screening result | Reuse services and add regression tests |
| Backup incomplete | Data loss | Backup manifest + restore test |
| Uninstall deletes data | Critical data loss | Default uninstall must preserve data |
| App opens local API to network | Privacy risk | Bind to 127.0.0.1 by default |
| Thai dates / normalized_visit_date remain null for old imports | Incorrect latest date | Re-import and regenerate after date fix |

---

## 14. Testing strategy

### 14.1 Regression tests required

Must test these business rules after Desktop migration:

1. Exact CID match works
2. Invalid CID not counted as no-history
3. Multi-sheet target-group file reads every sheet
4. History sheet contributes valid evidence
5. Mixed sheet contributes roster + history
6. Latest date is from selected service only
7. One person appears as one visible row
8. Provenance count/source preserved
9. Ambiguous identity marked needs review
10. Export matches visible result rules

### 14.2 Desktop-specific tests

- First launch creates database
- Data folder can be changed before first import
- Import Excel works
- Import PDF/CSV behavior unchanged if supported
- Backup creates complete zip
- Restore restores database and files
- Uninstall preserves data
- App restarts and sees previous data
- App works without internet
- App does not require Docker
- App does not require PostgreSQL installed
- App does not require Python/Node installed on user machine

### 14.3 Clean machine test

Test on Windows clean machine:

- No Docker
- No PostgreSQL
- No Python
- No Node.js
- Install `SeamlessFordMIS-Desktop-Setup.exe`
- Open app
- Import sample non-sensitive test files
- Generate result
- Export Excel
- Backup
- Restore
- Uninstall
- Confirm data preserved

---

## 15. Roadmap

### Phase D0 — Decision and scope lock

Goal:

- Approve Desktop Local Edition as separate edition
- Keep Docker/LAN Edition intact

Deliverables:

- This `PROJECT_ARCHITECTURE.md`
- Clear non-goals
- Confirmation that Desktop Local is single-user first

Non-goals:

- Do not remove Docker edition
- Do not rewrite matching/result generation
- Do not implement cloud sync
- Do not support multi-user SQLite over network share

### Phase D1 — Feasibility audit

Goal:

- Determine how much current backend depends on PostgreSQL/Docker

Tasks:

- Audit SQLAlchemy models
- Audit Alembic migrations
- Audit queries for PostgreSQL-specific syntax
- Audit file path assumptions
- Audit frontend API base assumptions
- Audit import/export service dependencies

Deliverables:

- `docs/DESKTOP_SQLITE_FEASIBILITY.md`
- Compatibility table: works / needs change / blocker
- Recommended migration approach

### Phase D2 — Local data layer prototype

Goal:

- Make backend boot with SQLite without Docker

Tasks:

- Add `DATABASE_ENGINE=sqlite`
- Add SQLite session config
- Add local paths config
- Create dev command for desktop backend
- Create minimal schema creation/migration path

Deliverables:

- Backend starts with SQLite
- `/health` works
- Basic API smoke works

### Phase D3 — Desktop shell prototype

Goal:

- Open app as one desktop program

Tasks:

- Choose shell technology
- Start local backend automatically
- Open embedded webview or browser window
- Stop backend on app close
- Show local data folder in settings

Deliverables:

- `SeamlessFordMIS Desktop` prototype
- No Docker required for prototype

### Phase D4 — Import/result workflow validation

Goal:

- Prove core hospital workflow works on SQLite

Tasks:

- Import screening database sample
- Import target group multi-sheet sample
- Generate result
- Review table
- Open detail modal
- Export Excel

Deliverables:

- Regression test report
- Bug list
- No business rule regression

### Phase D5 — Backup/restore for Desktop Local

Goal:

- Safe local backup/restore

Tasks:

- Backup SQLite + files into zip
- Add manifest
- Restore with confirmation
- Add warning that backup contains patient data
- Add restore test

Deliverables:

- Backup/restore UI
- Backup restore test report

### Phase D6 — Desktop installer

Goal:

- Build installer for non-technical users

Tasks:

- Create installer script
- Install app binaries
- Create shortcuts
- Create data folder
- Preserve data on uninstall
- Add first-run guide

Deliverables:

- `SeamlessFordMIS-Desktop-Setup.exe`
- Clean machine install test

### Phase D7 — Hardening and pilot

Goal:

- Prepare for real pilot with non-sensitive test data first

Tasks:

- Performance test with large Excel
- Backup/restore drill
- Crash/restart test
- UI wording review
- Data safety review
- Staff workflow review

Deliverables:

- Pilot readiness report
- Known limitations
- Training checklist

---

## 16. Codex instruction template

Use this command when assigning work to Codex:

```text
Read PROJECT_STATUS.md and PROJECT_ARCHITECTURE.md first.

Task: Work on Desktop Local Edition only.

Goal:
Make seamlessfordmis run as a single-machine desktop application without Docker by using SQLite and local file storage, while preserving all existing hospital screening business rules.

Before coding:
1. Summarize current project understanding.
2. Summarize Desktop Local Edition architecture.
3. Identify which files/services will be touched.
4. Identify risks to business rules.
5. Wait for confirmation if the change affects matching/result generation/import behavior.

Hard rules:
- Do not change exact CID priority.
- Do not ignore target-group-side history.
- Do not stop reading every sheet of target group Excel files.
- Visible result table must remain 1 person = 1 row.
- Preserve provenance without duplicating visible rows.
- Do not guess missing data.
- Do not use aggressive fuzzy matching.
- Do not remove Docker/LAN Edition.
- Do not commit patient data, real .env, database files, backups, uploaded files, or exports.

Desktop Local constraints:
- No Docker required.
- No PostgreSQL required.
- SQLite local database.
- Local data folder.
- Bind local API to 127.0.0.1 only unless explicitly enabling LAN mode.
- Backup must include SQLite DB + files + manifest.
- Uninstall must preserve data by default.

After work:
- Update PROJECT_STATUS.md.
- Update PROJECT_ARCHITECTURE.md if architecture changed.
- Summarize files changed.
- Summarize business logic changed or confirm none.
- Summarize tests run.
- Summarize blockers.
- Recommend next step.
```

---

## 17. Current recommendation

Phase D2 status as of 2026-05-27:

- Phase D1 feasibility audit is complete in `docs/DESKTOP_SQLITE_FEASIBILITY.md`.
- Runtime config now supports `APP_EDITION=desktop_local` and `DATABASE_ENGINE=sqlite`.
- Backend has a SQLite engine path with local PRAGMAs.
- Models use portable `GUID` / `JSONType` compatibility types instead of direct PostgreSQL UUID/JSONB model types.
- Desktop helper commands exist:
  - `python -m app.desktop.init_paths`
  - `python -m app.desktop.init_db`
- SQLite schema bootstrap uses `Base.metadata.create_all()` for prototype only.
- Production Desktop migration is still a future phase.
- Docker/LAN Edition remains the PostgreSQL path.

Updated recommended next move:

```text
Add regression tests and dialect-aware query helpers for import/result/export smoke on SQLite.
Do not build the Desktop shell or installer until backend workflow smoke is stable.
```

Recommended next move:

```text
Start Phase D1 — Desktop SQLite Feasibility Audit
```

Do not start full rewrite yet.

The safest first implementation task is:

```text
Audit database/model/query/migration compatibility with SQLite and produce docs/DESKTOP_SQLITE_FEASIBILITY.md
```

Only after that should the project create the actual Desktop Local prototype.

---

## 18. Final decision note

Desktop Local Edition is a good long-term direction because it matches the user goal:

```text
เปิดโปรแกรมเดียว
ไม่ต้องใช้ Docker
ใช้ทรัพยากรน้อยลง
เหมาะกับผู้ใช้ทั่วไป
ข้อมูลอยู่ในเครื่อง
ทำงาน offline ได้
```

But it must be implemented carefully as a separate edition, not by breaking the current Docker/LAN edition.
