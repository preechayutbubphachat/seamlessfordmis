# Desktop D4 Workflow Validation Plan

Date created: 2026-06-11
Status: **✅ D4 WORKFLOW VALIDATION = PASS (2026-06-16)** — Automated (Windows): G1 13 ✓ / G5 93 ✓ / desktop:build ✓ / tsc ✓. **Manual D4: M1–M9 PASS** (ผู้ใช้ทดสอบบน Windows 2026-06-16). Business logic changed = **No**. **ยังไม่เริ่ม EXE/Installer** — เป็นขั้น D5 หลังตัดสินใจ data-privacy git tracking
Manual results: M1 launcher/dashboard ✓ • M2 upload/double-submit ✓ • M3 duplicate upload handling ✓ • M4 service selection+generate ✓ • M5 F5/reopen selection restore ✓ • M6 TG-file evidence = info box (ไม่ใช่ red) ✓ • M7 no-history filter ไม่รวม TG-file case ✓ • M8 export category/แหล่งหลักฐาน ถูก ✓ • M9 close/reopen persistence ✓

## Manual D4 checklist (Windows, launcher เปิดอยู่)
| # | Step | Expected |
|---|---|---|
| M1 | เปิด dashboard | เห็นฐานข้อมูลการคัดกรอง (sync/seed แล้ว) |
| M2 | upload target group ไฟล์จริง (กดเดียว + กดรัว ๆ) | ไม่ database locked, ไม่ timeout 30s, ไม่ duplicate job |
| M3 | upload ไฟล์เดิม+ชื่อกลุ่มเดิมซ้ำ | ระบบ guide ไป group เดิม (409) ไม่สร้าง job ซ้ำ |
| M4 | step 4 เลือกบริการ → generate | เห็นรายการโรค/บริการ, generate สำเร็จ |
| M5 | เปิด result / reopen / F5 | selection restore ตรง, ไม่มี false mismatch warning, ไม่มี banner "สร้างผลลัพธ์ใหม่" (เว้นแต่ data/version เก่าจริง) |
| M6 | เปิดคนที่มี TG-file history (เช่น Z124/HPV DNA Test) | modal กล่องท้าย = **info box** "พบประวัติจากไฟล์กลุ่มเป้าหมาย" (ไม่ใช่ red error), latest date ถูก |
| M7 | filter "ยังไม่เคยตรวจ/ไม่มีประวัติ" | **ไม่รวม**คนที่มี TG-file history |
| M8 | export Excel | มีคอลัมน์ "สถานะผลลัพธ์" + "แหล่งหลักฐาน" ถูกต้อง |
| M9 | ปิด/เปิด launcher ใหม่ | persistence + flow ยังทำงาน |

ครบ M1–M9 → **D4 workflow validation = PASS** → เริ่มพิจารณา D5

## D4.7.5 fix round (2026-06-16) — false result-mismatch / selection not restored

### Root cause (frontend)
`TargetGroupResultsWorkspace.tsx`: เปิดกลุ่มที่ไม่มี `?services=` ใน URL → selection fallback เป็น option แรก แทน restore จาก `summary.selected_service_keys` → `isDirty` true → false warning. Backend persist ถูกต้อง (ไม่แตะ).

### Files changed (business logic ไม่เปลี่ยน)
- `frontend/.../TargetGroupResultsWorkspace.tsx` — restore selection จาก summary ลง URL (ครั้งเดียว, guard ref) + summary แสดง label แทน raw key

### Verify
- backend ไม่แตะ (G1/G5 ไม่กระทบ). tsc/manual ต้องรันบน Windows (sandbox mount truncate ไฟล์ใหญ่). Business logic=No. D4=NO-GO.

### Round-6 manual test (Windows) — selection persistence
| # | Step | Expected |
|---|---|---|
| S1 | `cd frontend && npm run desktop:build && npx tsc --noEmit` | ผ่าน |
| S2 | launcher → เปิดกลุ่ม → step 4 เลือกหลายบริการ (เช่น cervical+HPV+specimen) → generate | result table แสดง |
| S3 | ไป step 5 → กลับมาเปิดกลุ่ม/หน้า result | selection restore ตรงกับที่ generate (ติ๊กครบ), **ไม่มี false warning** |
| S4 | F5 ที่หน้า result | selection ยังตรง, ไม่มี warning |
| S5 | close/reopen launcher → เปิดกลุ่มเดิม | selection ยัง restore จาก summary |
| S6 | เปลี่ยน selection จริง (ติ๊กออก/เพิ่ม) | warning "ผลลัพธ์ไม่ตรงกับรายการที่เลือก" ขึ้นถูกต้อง + ปุ่มสร้างผลลัพธ์ใหม่ |
| S7 | summary "บริการที่เลือก" | แสดง label อ่านง่าย (ไม่ใช่ raw key) |
| S8 | latest date ในตาราง | ยังมาจาก selected service เท่านั้น (ไม่เปลี่ยน) |

## D4.7.4 fix round (2026-06-16) — empty disease/service options

### Root cause
`disease-options` มาจากตาราง seed `disease_mapping` (ไม่ใช่ screening records). `init_db()` desktop ทำแค่ create_all ไม่ seed → ตารางว่าง → options `[]`. sync screening ไม่ช่วย (คนละตาราง).

### Files changed (ไม่แตะ business logic)
- `backend/app/seeds/disease_mapping_seed.py` — `seed_disease_mapping_if_empty()` (idempotent, ไม่ wipe)
- `backend/app/db/init_db.py` — desktop+sqlite เรียก seed-if-empty หลัง create_all
- `backend/app/services/source_sync_service.py` — system status เพิ่ม `disease_mapping`/`active_disease_mapping` count
- `frontend/.../detail/page.tsx` + `TargetGroupUploadForm.tsx` — empty-state ข้อความถูกต้อง + ปุ่ม Dashboard
- `backend/tests/test_disease_mapping_seed.py` (ใหม่)

### Verify
- inline: ก่อน seed options=0 → หลัง seed=18 (catalog จริง). G1=13, G5=87 (3 fail = sandbox mount artifact, ไฟล์จริงครบ). Business logic=No. D4=NO-GO จนกว่าจะผ่าน Windows.

### Round-5 manual test (Windows) — disease options
| # | Step | Expected |
|---|---|---|
| O1 | `cd frontend && npm run desktop:build && npx tsc --noEmit` | ผ่าน |
| O2 | `cd ..\backend && pytest tests/ -q` | G1 13 + G5 ครบ (รวม test ใหม่) |
| O3 | `python -m app.desktop.launch` (DB ใหม่/ว่าง) | auto-seed disease_mapping |
| O4 | `Invoke-RestMethod .../api/system/status` → `row_counts.disease_mapping` | > 0 |
| O5 | `Invoke-RestMethod .../api/target-groups/disease-options` | array ไม่ว่าง |
| O6 | target group → step 4 | เห็นรายการโรค/บริการ |
| O7 | เลือก service → generate → result table → export | ผ่านครบ |
| O8 | F5 + close/reopen | persistence ปกติ |

## D4.7.3 fix round (2026-06-16) — upload timeout/reconciliation (large file)

### Root cause
`uploadTargetGroupFiles()` ใช้ default read timeout 30s — upload 21,309 rows ใช้ >30s → frontend ยกเลิกก่อน backend จบ (backend commit สำเร็จ). retry เสี่ยง duplicate job (ไม่มี hash guard).

### Files changed (ไม่แตะ business logic)
- `frontend/src/lib/api.ts` — mutation timeout 180s (upload/add-files/screening upload/sync/confirm/run-match); reads 30s.
- `frontend/.../TargetGroupUploadForm.tsx` — reconciliation หลัง timeout (หา group ตาม group_name, ไม่ auto-retry) + ปุ่มเปิดกลุ่ม + 409 handling + ข้อความ friendly.
- `backend/app/services/target_group_import_service.py` — `DuplicateUploadError` + guard (source_set_hash + group_name).
- `backend/app/api/target_groups.py` — timing log + 409 mapping พร้อม existing group_id.
- `backend/tests/test_target_group_duplicate_guard.py` (ใหม่).

### Verify status
- รอบนี้ sandbox verify ไม่ครบ (bash mount truncate ไฟล์ใหญ่ระหว่าง sync → tsc/pytest error ปลอม). ไฟล์จริงครบถูกต้อง (ยืนยันผ่าน Read tool). ต้อง verify บน Windows. Business logic = No. D4 = NO-GO จนกว่าจะผ่าน Round 4.

### Round-4 manual test (Windows) — large-file upload
| # | Step | Expected |
|---|---|---|
| U1 | `cd frontend && npm run desktop:build && npx tsc --noEmit` | ผ่าน |
| U2 | `cd ..\backend && python -m compileall app -q && pytest tests/ -q` | ผ่านหมด (รวม duplicate guard) |
| U3 | launch → upload ไฟล์ 21,309 rows กดครั้งเดียว | **ไม่ timeout ที่ 30s**; ถ้านานเห็น progress/elapsed |
| U4 | ถ้านานกว่า backend จริง → timeout 180s | reconcile: "พบงานนำเข้าล่าสุดแล้ว" + ปุ่มเปิดกลุ่ม (ไม่สร้าง job ซ้ำ) |
| U5 | กด upload เดิมซ้ำ (ชื่อ+ไฟล์เดิม) | 409 → guide ไป group เดิม, **ไม่มี duplicate target_group_jobs** |
| U6 | upload → validate → generate → export | ผ่านครบ |
| U7 | F5 + close/reopen | persistence ปกติ |
| U8 | ตรวจ backend log | เห็น `upload_files.done duration_ms=...` (ตอบได้ว่า 21,309 rows ใช้กี่วินาที) |

## D4.7.2 fix round (2026-06-16) — SQLite "database is locked" on upload

### Root cause
- `upload_files()` ถือ SQLite write lock ตลอด (flush job → parse Excel → commit) ใน transaction เดียว + engine ไม่มี `busy_timeout` → write ที่ชน lock fail ทันที + ไม่มี application-level serialization (double-submit ชนกัน).

### Files changed (ไม่แตะ business logic)
- `backend/app/db/session.py` — `PRAGMA busy_timeout=30000` + `connect_args timeout=30s` (sqlite only).
- `backend/app/db/write_lock.py` (ใหม่) — `sqlite_write_lock()` + `WriteBusyError` (no-op บน PostgreSQL).
- `backend/app/api/target_groups.py` — wrap upload-files/add-files/confirm-import/run-match/generate-results.
- `backend/app/api/imports.py` — wrap sync-main-dataset.
- `backend/app/main.py` — `WriteBusyError`→423, `OperationalError` locked→503 friendly (ไม่ leak raw SQL).
- `frontend/.../TargetGroupUploadForm.tsx` — double-submit guard + `[upload]` log.
- `backend/tests/test_desktop_sqlite_concurrency.py` (ใหม่) — 6 tests.

### Tests run (sandbox)
- compileall clean • `test_desktop_sqlite_workflow.py` 13 passed (G1) • suite 86 passed (G5 + concurrency 6) → **99 passed / 0 failed** • `npx tsc --noEmit` clean • `npm run desktop:build` ต้องรันบน Windows.
- Business logic changed = **No** • D4 workflow validation = **NO-GO จนกว่าจะผ่าน Windows re-test รอบ 4**.

### Round-4 manual test (Windows) — database lock
| # | Step | Expected |
|---|---|---|
| K0 | ปิด launcher/process ค้าง: `Get-Process python`, `Get-NetTCPConnection -LocalPort 8010` (kill เฉพาะ launcher/backend) | ไม่มี process ค้าง / port ว่าง |
| K1 | `cd frontend && npm run desktop:build && npx tsc --noEmit` | ผ่าน |
| K2 | `python -m app.desktop.launch` → upload target group กดครั้งเดียว | ไม่ database locked, ได้ preview |
| K3 | กด "อัปโหลดและตรวจตัวอย่าง" รัว ๆ เร็ว ๆ | ไม่ locked, ไม่เกิด duplicate target_group_jobs, ถ้าชนได้ข้อความ busy ที่อ่านง่าย |
| K4 | ตรวจว่าไม่มี raw SQL ยาวโผล่ใน UI | เห็นเฉพาะข้อความภาษาไทยอ่านง่าย |
| K5 | upload → validate → generate → export ต่อเนื่อง | ผ่านครบ ไม่ locked |
| K6 | F5 reload หน้า detail | โหลดกลับมาเอง |
Debug aid: ถ้า fail ให้เปิด DevTools Console แล้ว copy บรรทัด `[tg-detail]`, `[api]` และ `[progress]` กลับมา (log ไม่มี patient identifier)
Data policy: **synthetic fixtures เท่านั้น** (`backend/tests/fixtures/desktop_local/`) — ห้ามใช้ข้อมูลผู้ป่วยจริง

## D4.7.1 fix round (2026-06-15) — loading stuck + progress + overflow

### Root cause (loading ค้างเงียบ)
1. `frontend/src/components/target-groups/TargetGroupUploadForm.tsx` (step 4 "สร้างผลลัพธ์"): โหลด disease options ด้วย `getDiseaseOptions().then().catch(() => {})` — **catch กลืน error ทิ้ง** และ render เช็คแค่ `diseaseOptions.length > 0`. ทำให้ API fail / hang / empty ทั้งหมดแสดง "กำลังโหลดรายการบริการ..." ค้างตลอด แยกไม่ออกระหว่าง loading / error / empty.
2. `frontend/src/lib/api.ts` `request()`: **ไม่มี timeout** (fetch ไม่มี AbortController) → ถ้า backend/DB ค้าง ทุกหน้าจะ loading ไม่รู้จบ.

### Files changed (frontend loading/state/UI เท่านั้น — ไม่แตะ backend business logic)
- `frontend/src/lib/api.ts` — เพิ่ม AbortController hard timeout (read 30s, generate-results 180s), เพิ่ม `ApiErrorKind = "network" | "backend" | "timeout"`, log durationMs (path only, no query/CID).
- `frontend/src/components/common/useElapsedSeconds.ts` (ใหม่) — นับวินาทีสำหรับ elapsed + slow-loading notice.
- `frontend/src/components/common/StageProgress.tsx` (ใหม่) — stage-based progress: progress bar + "ขั้นตอน X/Y" + elapsed + slow notice (15s) + retry + error state. ระบุชัด "ความคืบหน้าตามขั้นตอน (ไม่ใช่จำนวนรายการจริง)".
- `frontend/src/components/target-groups/TargetGroupUploadForm.tsx` — step 4 มี optionsStatus (idle/loading/success/error) + retry + empty state แยกจาก error; ปุ่มสร้างผลลัพธ์มี stage progress 7 ขั้น + double-fire guard + retry on fail; debug log `[tg-detail]`.
- `frontend/src/app/target-groups/detail/page.tsx` — หน้า detail loading ใช้ StageProgress 5 ขั้น + elapsed + retry.
- `frontend/src/app/globals.css` — overflow guard: `html,body { max-width:100%; overflow-x:hidden }`, `.main-column { overflow-x:clip }`, `.app-shell/.panel { max-width:100% }`. ตาราง/stepper ยังมี scroll container ของตัวเอง (ไม่ทำข้อมูลหาย).

### Behavior หลังแก้
- ทุก fetch จบด้วย success / empty / error / timeout — ไม่มี loading ไม่รู้จบ.
- โหลดเกิน 15 วินาที → "โหลดนานกว่าปกติ กดลองใหม่หรือตรวจสอบฐานข้อมูลการคัดกรอง" + ปุ่ม "ลองโหลดใหม่".
- API fail → error จริง (ไม่ใช่ empty); empty state ใช้เฉพาะ API สำเร็จแต่ไม่มีข้อมูล.
- Business logic / matching / result generation / import rules / CID validation / provenance: **ไม่เปลี่ยน**.

### Verification status
- TypeScript/build verify ในแซนด์บ็อกซ์รันไม่ได้ (mount sync limitation) → **ต้องรันบน Windows** (ดู Round-3 manual test ด้านล่าง).
- D4 workflow validation = **NO-GO จนกว่าจะผ่าน Windows re-test รอบ 3**.

## Round-3 manual test (Windows) — loading/progress/overflow
| # | Step | Expected |
|---|---|---|
| L1 | `cd frontend && npm run desktop:build` | build ผ่าน, ได้ `frontend/out/` |
| L2 | `npx tsc --noEmit` (ใน frontend) | ไม่มี error |
| L3 | `python -m app.desktop.launch` → เปิด dashboard | เปิดหน้าแอปจริง |
| L4 | เข้าเมนูกลุ่มเป้าหมาย → ไปขั้น "สร้างผลลัพธ์" | เห็น stage progress + elapsed ไม่ค้างเงียบ |
| L5 | ถ้าฐานตรวจโรคมีข้อมูล | รายการโรค/บริการขึ้นเอง |
| L6 | ถ้า backend/DB ปิด | เห็น error + ปุ่มลองโหลดใหม่ (ไม่ค้าง) |
| L7 | กดสร้างผลลัพธ์ | เห็น stage progress 7 ขั้น, ปุ่ม disabled ระหว่างทำงาน, จบด้วย success/error |
| L8 | เปิดหน้า detail แล้ว F5 | โหลดกลับมาเอง (stage progress 5 ขั้น) |
| L9 | ปิด/เปิด launcher ใหม่ | flow ยังทำงาน |
| L10 | ตรวจ horizontal scrollbar ที่ 1366×768 / 1440×900 / 1920×1080 | ไม่มี scrollbar แนวนอนระดับหน้า (ตารางกว้าง scroll ใน container เท่านั้น) |

## Pre-requisites

1. `cd frontend && npm run desktop:build` → ได้ `frontend/out/`
2. `backend\scripts\check_desktop_launcher.bat` ผ่าน (D3.1 PASSED แล้ว 2026-06-11)

## Validation steps (ทำตามลำดับ บันทึกผลทุกข้อ)

| # | Step | Expected | Business rule |
|---|---|---|---|
| 1 | `python -m app.desktop.launch` | start สำเร็จ, opened_url = `http://127.0.0.1:8010/` | — |
| 2 | Browser เปิดหน้าแอปจริง (dashboard) | ไม่ใช่ /docs | — |
| 3 | `curl http://127.0.0.1:8010/health` | desktop_local + sqlite | — |
| 4 | Import screening sample (synthetic) ผ่านหน้า dashboard | staged + ไม่มี error | raw values preserved |
| 5 | Upload target group multi-sheet fixture (`target_group_multisheet.xlsx`) | อ่านทุก sheet: roster + history | rule 4 |
| 6 | Generate results เลือกโรค/บริการ | สำเร็จ | — |
| 7 | ตรวจ result table | **1 คน = 1 แถว** ไม่มีแถวซ้ำจาก provenance | rules 7, 8 |
| 8 | ตรวจ person ที่มี history ฝั่ง target group file เท่านั้น | นับเป็น has_selected_service ไม่ใช่ no-history | rule 5 |
| 9 | ตรวจ latest date | มาจากโรค/บริการที่เลือกเท่านั้น (EVE case: cervical 2022-05-01 ≠ diabetes 2023-12-20) | rule 6 |
| 10 | ตรวจ invalid CID row (`1234567890000`) | `invalid_identifier` มองเห็นใน staging ไม่ใช่ no-history เงียบ ๆ | rules 2, 3 |
| 11 | Export Excel | ไฟล์ตรงกับผลบนจอ ไม่ใช่ fake export | rule 10 |
| 12 | ปิด launcher (Ctrl+C) | port 8010 released | — |
| 13 | เปิด launcher ใหม่ | data เดิมยังอยู่ (SQLite persist) | — |

## Pass criteria

ทุกข้อผ่าน → D4 workflow validation = PASSED → จึงเริ่มพิจารณา D5 (packaging/installer planning) ได้
ข้อใดไม่ผ่าน → บันทึก step + actual vs expected + screenshot แล้วรายงานก่อนแก้

## Out of scope (ห้ามทำใน D4)

- EXE/Installer เต็มรูปแบบ
- Clean machine test (D5)
- ข้อมูลผู้ป่วยจริง
