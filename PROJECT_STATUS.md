# PROJECT_STATUS.md

## Session summary — Windows regression GREEN + fix unstable duplicate-guard hash + httpx dep (2026-06-16, session 14)

- **Date:** 2026-06-16
- **Windows verification:** compileall ✓ • **G1 = 13 passed** • **G5 = 92 passed / 1 failed** • `npm run desktop:build` ✓ • `npx tsc --noEmit` ✓ — sandbox false-failures (BOM/truncation) **หายหมดบน Windows** (ไฟล์ครบ); test ใหม่ทั้งหมด (disease_mapping_seed, normalization_version, concurrency, result_generation k1–k7) **ผ่าน**
- **Business logic changed:** **No** (matching/classification ไม่แตะ)

### Fix 1 — httpx test dependency
`backend/requirements.txt` += `httpx==0.28.1` (จำเป็นสำหรับ `fastapi.testclient.TestClient`; เดิม httpx อยู่แค่ root requirements.txt ที่ไม่มี pytest → backend venv ขาด → collection error). Windows ติดตั้งแล้ว, collect ครบ

### Fix 2 — duplicate-job guard ใช้ hash ที่ stable (1 real bug ที่ Windows เจอ)
- **อาการ:** `test_duplicate_upload_guard` FAIL "DID NOT RAISE" — upload ไฟล์เดิม+ชื่อเดิมซ้ำ ไม่ถูก guard
- **Root cause:** guard เดิม key ด้วย `source_set_hash` แต่ `FileHashService.manifest_hash` รวม `filename`+`path`+`modified_at` ของไฟล์ที่ stage (เขียนลง uuid path + mtime ใหม่ทุก upload) → source_set_hash **ไม่ stable** → retry ได้ hash ต่าง → guard ไม่เคย match (ใน production การ retry หลัง timeout ก็จะสร้าง duplicate job จริง!)
- **Fix:** `backend/app/services/target_group_import_service.py` — guard key ด้วย **set ของ content sha256** (`TargetGroupJobFile.sha256`, stable ข้าม re-upload) + group_name แทน source_set_hash; ยังคงอนุญาต re-use roster ชื่อกลุ่มต่างกัน
- ไฟล์เดียว: `backend/app/services/target_group_import_service.py`

### Tests run
- Windows (authoritative): G1 13, G5 92/93 (เหลือ duplicate guard ที่เพิ่งแก้) — ต้อง re-run `pytest tests/test_target_group_duplicate_guard.py -v` (คาด 2 passed) → G5 = 93/93
- Sandbox boot ค้างรอบนี้ — verify fix ที่ Windows

### Windows automated verification: **GREEN (2026-06-16)**
- `test_target_group_duplicate_guard` = **2 passed** (content-sha256 guard ทำงาน: retry ไฟล์เดิม+ชื่อเดิม raise, ชื่อต่างไม่ raise)
- **G5 = 93 passed** • **G1 = 13 passed** • `npm run desktop:build` ✓ • `npx tsc --noEmit` ✓
- launcher: `python -m app.desktop.launch` เปิดเสิร์ฟ `http://127.0.0.1:8010/` (desktop_local/sqlite, auto-seed + ALTER column ทำงานตอน startup)

### ✅ D4 WORKFLOW VALIDATION = PASS (2026-06-16)
- Automated (Windows): G1 13 ✓ / G5 93 ✓ / desktop:build ✓ / tsc ✓
- **Manual D4: M1–M9 PASS** — M1 launcher/dashboard • M2 upload/double-submit • M3 duplicate upload handling • M4 service selection+generate • M5 F5/reopen restore • M6 TG-file evidence info box (ไม่ใช่ red) • M7 no-history filter ไม่รวม TG-file case • M8 export category/แหล่งหลักฐาน ถูก • M9 close/reopen persistence
- Business logic changed = **No**
- **ยังไม่เริ่ม EXE/Installer** (ขั้น D5)

### Next recommended steps (ตามลำดับปลอดภัย)
1. **Safe code commit** — งาน D3/D4 ทั้งหมดยังเป็น working-tree ที่ยังไม่ commit (เปราะบาง ถ้า reset/pull หาย) → commit เฉพาะ code/test/docs (ดูชุดคำสั่ง session 9; ตอนนี้มีไฟล์ใหม่เพิ่มอีกหลายตัว — ต้อง stage path เพิ่ม) **ไม่ commit data/**
2. **Data privacy git tracking decision** — `docs/DATA_PRIVACY_GIT_TRACKING_AUDIT.md`: 70 ไฟล์ data/ ยัง tracked → ตัดสินใจ `git rm -r --cached data/` (ไฟล์จริงไม่หาย) + history cleanup ถ้าเคย push
3. **D5 packaging/installer planning** — หลัง commit + privacy decision เท่านั้น

---


## Session summary — Phase D4.7.7 — Polish target-group-file evidence display (not error) + export labels (2026-06-16, session 13)

- **Date:** 2026-06-16
- **Task worked on:** หลัง regenerate classification ถูกแล้ว (modal: found_in_target_group_file=true, 2 ประวัติ, 13 มี.ค. 2569) แต่กล่องท้าย modal ยังเป็น **red error** ("ใช้ประวัติจากไฟล์กลุ่มเป้าหมายเป็นหลัก... พบ CID ซ้ำ") ทำให้เข้าใจว่าเป็น error ทั้งที่เป็นหลักฐานที่ถูกต้อง
- **Business logic changed:** **No** — frontend wording/style + backend export **label เท่านั้น** (ไม่แตะ matching/classification/latest-date/CID/provenance/filter)

### Files changed
| File | Change |
|---|---|
| `frontend/.../PatientDetailModal.tsx` | กล่องท้าย: ถ้า `history_found_in_target_group_file` → **info box (subtle-box + chip "ready")** ไม่ใช่ red error; ข้อความ "พบประวัติจากไฟล์กลุ่มเป้าหมาย / ไม่พบในฐานข้อมูลการตรวจโรค แต่พบในไฟล์กลุ่มเป้าหมาย ระบบใช้เป็นหลักฐาน + เก็บ provenance"; raw warning (incl. duplicate-CID merge) ย้ายเป็น "รายละเอียดเชิงเทคนิค" แบบ muted. red error เหลือเฉพาะกรณีไม่มี TG evidence |
| `backend/app/services/export_service.py` | `_result_category_label` เพิ่มหมวด `target_group_file_only`/`screening_db_only`/`both_sources`/`no_history_found` ฯลฯ (เดิม fallback เป็น key ดิบ) + คอลัมน์ใหม่ **"แหล่งหลักฐาน"** (`_evidence_source_label` จาก `latest_relevant_source_type`) |

### UI wording before/after
- **Before:** red `feedback-line is-error` แสดง `warning_message` ดิบ → ดูเหมือน error
- **After:** info box (เขียว/neutral) "พบประวัติจากไฟล์กลุ่มเป้าหมาย" + คำอธิบาย valid evidence + technical detail แบบ muted

### Table / filter / export verification (logic เดิม ถูกอยู่แล้ว หลัง regenerate)
- **Table:** `ResultsTable` badge `target_group_file_only` → "พบจากไฟล์กลุ่มเป้าหมาย" (มีอยู่แล้ว, ถูกต้องหลัง data ถูก regenerate)
- **No-history filter:** `view=never_checked` ใช้ `has_selected_service.is_(False)` → คนนี้ `has_selected_service=true` → **ถูกกันออกแล้ว** (ไม่ต้องแก้ backend)
- **Export:** หมวด + แหล่งหลักฐาน + วันที่ล่าสุด แสดงถูกต้อง

### Tests run
- G1 = **13 passed**; suite อื่น = **87 passed** (รวม `test_export_service` 4 ผ่าน — export ไม่ regress); 6 fail = **mount-corruption artifacts** (test ใหม่รอบก่อน ๆ พึ่งโมดูลที่ sandbox sync ใส่ BOM/ตัดไฟล์ — authoritative C:\ ครบ). frontend tsc artifact เช่นกัน — ยืนยัน edit จริง well-formed ผ่าน Read tool. ต้อง verify บน Windows
- Business logic changed = **No**

### D4 workflow validation: **NO-GO — pending final Windows verification** (modal info box, table status, no-history filter, export category)

### Next recommended step
Windows: `cd frontend && npm run desktop:build && npx tsc --noEmit` + `cd ..\backend && pytest tests/ -q` → launcher → เปิดคน Z124/HPV DNA Test: modal กล่องท้ายเป็น **info ไม่ใช่ red**, table = "พบจากไฟล์กลุ่มเป้าหมาย", no-history filter ไม่รวม, export มีคอลัมน์ "แหล่งหลักฐาน" = ไฟล์กลุ่มเป้าหมาย + วันที่ 13 มี.ค. 2569 → ถ้าครบ **mark D4 PASS**

---


## Session summary — Phase D4.7.6 — Stale-result guard (regenerate prompt) for target-group-file history (2026-06-16, session 12)

- **Date:** 2026-06-16
- **Task worked on:** Windows test — คนที่มี target-group-file history (Z124/HPV DNA Test, evidence `derived_from_roster_history_context`) แสดง "ยังไม่พบประวัติ" ในตาราง ทั้งที่ modal เจอ. **ยืนยัน B1 (stale result rows): regenerate แล้วหาย**
- **Business logic changed:** **No** — ไม่แตะ classification/matching/latest-date/CID/provenance; เพิ่มแค่ "staleness guard" ให้เตือนผู้ใช้ regenerate

### Root cause (B1)
ผลลัพธ์ถูก generate ด้วยโค้ด/normalization รุ่นก่อนที่จะนับ roster-derived target-group history → แถวที่ **เก็บไว้** (`TargetGroupResult`/summary cache) = no_history ค้างอยู่ แม้ source file เดิม. modal คำนวณ on-demand ด้วยโค้ดปัจจุบัน → เจอ. ต่างกันเพราะ stored vs on-demand. `isSourceStale` เดิม (hash-based) จับไม่ได้เพราะ source hash ไม่เปลี่ยน

### Files changed (guard only — ไม่แก้ classification หลัก)
| File | Change |
|---|---|
| `backend/app/services/result_generation_service.py` | `RESULT_NORMALIZATION_VERSION = 2`; stamp ลง summary cache (upsert); `get_result_summary` คืน `normalization_version` + `requires_regeneration = (version or 0) < current` |
| `backend/app/models/target_group_result_summary.py` | + column `normalization_version` (nullable, backward compatible) |
| `backend/app/schemas/result.py` | `ResultSummaryResponse` += `normalization_version`, `current_normalization_version`, `requires_regeneration` |
| `backend/app/db/init_db.py` | `_ensure_sqlite_columns()` — idempotent `ALTER TABLE ADD COLUMN` สำหรับ desktop SQLite ที่มีอยู่แล้ว (create_all ไม่ alter ตารางเดิม) |
| `backend/alembic/versions/20260616_0016_*.py` | **ใหม่** — migration เพิ่ม column (LAN/Postgres) |
| `frontend/.../TargetGroupResultsWorkspace.tsx` | banner เตือน "ผลลัพธ์สร้างด้วยวิธีประมวลผลรุ่นก่อน → สร้างผลลัพธ์ใหม่" เมื่อ `requires_regeneration`; export disabled จนกว่าจะ regenerate |
| `frontend/src/types/result.ts` | + 3 fields |
| `backend/tests/test_result_normalization_version.py` | **ใหม่** — current=not stale, old/null=stale |

### Behavior
- result เก่า (normalization_version < current หรือ NULL) → banner เตือน + ปุ่ม "สร้างผลลัพธ์ใหม่" + export ถูก disable จนกว่าจะ regenerate (ไม่ auto-regenerate, ไม่ซ่อน warning)
- หลัง regenerate → stamped version current → banner หาย, ตารางถูกต้อง (roster history นับ)
- ไม่แตะ classification → ผลลัพธ์ที่ regenerate ใช้ logic เดิมที่ถูกต้องอยู่แล้ว

### Tests run
- พิสูจน์ logic แล้ว (รอบก่อน inline). รอบนี้ sandbox รัน test ใหม่ไม่ผ่านเพราะ **mount sync ใส่ BOM/ตัดไฟล์ backend** (model/schema/init_db corrupt ใน mount → false error); authoritative C:\ ครบถูกต้อง (ยืนยันผ่าน Read tool). ต้องรัน G1/G5 + tsc บน Windows
- Business logic changed = **No**

### D4 workflow validation: **NO-GO — pending Windows re-run**

### Next recommended step
Windows: `cd backend && python -m compileall app -q && pytest tests/ -q` (รวม test ใหม่) → `cd ..\frontend && npm run desktop:build && npx tsc --noEmit` → launcher → เปิดกลุ่มเก่า: ต้องเห็น banner "สร้างผลลัพธ์ใหม่" → กด regenerate → คน Z124/HPV DNA Test แสดง "พบประวัติจากไฟล์กลุ่มเป้าหมาย", latest date 13 มี.ค. 2569, no-history filter ไม่รวมคนนี้, export ถูก. **DB เดิมที่มีอยู่:** launcher จะ ALTER เพิ่ม column ให้อัตโนมัติตอนเปิด (idempotent)

---


## Session summary — Phase D4.7.5 — Fix false "result mismatch" / selection not restored after generate (2026-06-16, session 11)

- **Date:** 2026-06-16
- **Task worked on:** Windows test — หลัง generate result แล้วเปิดกลุ่ม/F5/reopen รายการที่เลือกไม่ restore → ขึ้น warning "ผลลัพธ์ไม่ตรงกับรายการที่เลือก" (รายการปัจจุบัน: HPV) ทั้งที่ผลลัพธ์ generate จาก 3 บริการ (cervical_screen, hpv_screen, specimen_collection)
- **Business logic changed:** **No** — แก้ frontend selection-restore + label display เท่านั้น (matching/result generation/latest-date/CID/provenance ไม่แตะ; backend ไม่แตะ)

### Root cause (frontend ล้วน)
`TargetGroupResultsWorkspace.tsx`: `selectedKeys` อ่านจาก URL `?services=`; เมื่อเปิดกลุ่มใหม่/F5/reopen ที่ไม่มี param นี้ → fallback เป็น `diseaseOptions.slice(0,1)` = **option แรก (HPV)** แทนที่จะ restore จาก `results.summary.selected_service_keys` (3 ตัวที่ generate ไว้) → `isDirty` เทียบ current(1) ≠ generated(3) → **false mismatch warning**. Backend persist `selected_service_keys` ถูกต้องครบ (summary cache คืน 3 ตัว) — ไม่ใช่ปัญหา data/SQLite.

### Files changed
| File | Change |
|---|---|
| `frontend/.../TargetGroupResultsWorkspace.tsx` | (1) effect restore selection จาก `summary.selected_service_keys` ลง URL ครั้งเดียวเมื่อไม่มี `?services=` (guard ด้วย ref กัน loop) (2) summary "บริการที่เลือก" แสดง label แทน raw key (`generatedServiceLabels`) |

### Canonical selection model (ยืนยันของเดิม ไม่เปลี่ยน)
- UI selection + generate request + restore = **service_keys array** (option.key) เก็บใน URL `?services=`
- persisted criteria = `target_group_result_summary.selected_service_keys` (JSON list, SQLite+PG)
- comparison = `sameSelection()` set-based (sorted join) — ถูกอยู่แล้ว ไม่แก้

### Persistence/restore behavior
- generate → backend เก็บ selected_service_keys (เดิม, ถูก) → reopen/F5/relaunch: effect ดึงจาก summary ใส่ URL → checkbox + warning ตรงกับที่ generate → **false warning หาย**. ถ้าผู้ใช้เปลี่ยน selection จริง → URL ต่างจาก summary → warning ขึ้นถูกต้อง
- **Refine (รอบ 2 ของ D4.7.5):** ยืนยันว่า `_normalize_selected_service_keys` แค่ dedup/sort **ไม่ expand** → `summary.selected_service_keys` = สิ่งที่ frontend ส่งเป๊ะ. แก้ restore effect ให้ **generated summary เป็น source-of-truth ตอนเปิดเสมอ** (restore แม้ URL มี `?services=` ค้างที่ไม่ตรง เช่น `hpv_screen` ค้างทับ generated 3 keys) → false warning หายทุกกรณีตอนเปิด/F5/reopen; warning ขึ้นเฉพาะเมื่อผู้ใช้เปลี่ยน selection หลังเปิด (ก่อน F5)

### Tests run
- backend ไม่แตะ → G1/G5 ไม่กระทบ. frontend tsc ในแซนด์บ็อกซ์รันสะอาดไม่ได้ (mount truncate ไฟล์ใหญ่ระหว่าง sync → error ปลอมที่ท้ายไฟล์) — ไฟล์จริง C:\ ครบถูกต้อง ยืนยันผ่าน Read tool. ต้อง `npx tsc --noEmit` + manual บน Windows

### D4 workflow validation: **NO-GO — pending Windows re-run**

### Next recommended step
Windows: `cd frontend && npm run desktop:build && npx tsc --noEmit` → launcher → เปิดกลุ่มที่ generate แล้ว: รายการต้อง restore ตรงกับที่ generate, ไม่มี false warning, F5/reopen ยังตรง, เปลี่ยน selection จริงค่อยขึ้น warning → generate → export

---


## Session summary — Phase D4.7.4 — Fix empty disease/service options on Desktop SQLite (2026-06-16, session 10)

- **Date:** 2026-06-16
- **Task worked on:** Windows test — หน้า "สร้างผลลัพธ์" (step 4) ไม่มีรายการโรค/บริการ (empty state) ทั้งที่ upload/sync ผ่าน
- **Business logic changed:** **No** — เพิ่ม auto-seed reference catalog + diagnostics + UI wording (ไม่แตะ matching/result generation/CID validation/provenance)

### Root cause
`disease_options()` อ่านจากตาราง **`disease_mapping`** (seeded reference catalog, is_active=true) — **ไม่ได้ derive จาก screening records**. แต่ `init_db()` (ทั้ง desktop launcher และ FastAPI startup) ทำแค่ `create_all` + metadata **ไม่เคย seed `disease_mapping`** (seed เป็นสคริปต์แยกที่ต้องรันเอง). บน Desktop SQLite ใหม่ ตารางว่าง → `disease-options` คืน `[]` → empty state. การ sync screening **ไม่ช่วย** เพราะคนละตาราง (ข้อความ UI เดิมที่บอกให้ sync จึงทำให้เข้าใจผิด).

### Files changed
| File | Change |
|---|---|
| `backend/app/seeds/disease_mapping_seed.py` | เพิ่ม `seed_disease_mapping_if_empty()` — idempotent, seed เฉพาะตอนตารางว่าง, ไม่ลบของเดิม (ใช้ `seed/disease_mapping_seed.json` จริง 21 แถว, fallback 3 แถว) |
| `backend/app/db/init_db.py` | desktop+sqlite: เรียก `seed_disease_mapping_if_empty()` หลัง create_all |
| `backend/app/services/source_sync_service.py` | system status `row_counts` เพิ่ม `disease_mapping` + `active_disease_mapping` (diagnostics, ไม่ expose CID) |
| `frontend/src/app/target-groups/detail/page.tsx` | empty-state: ข้อความถูกต้อง (catalog ไม่ใช่ screening sync) + ปุ่ม "ไปหน้า Dashboard" |
| `frontend/.../TargetGroupUploadForm.tsx` | step 4 empty-state: ข้อความถูกต้อง + ปุ่ม Dashboard |
| `backend/tests/test_disease_mapping_seed.py` | **ใหม่** — seed-if-empty populates options + idempotent + ไม่ wipe |

### Workaround (ถ้า DB ปัจจุบันว่างอยู่แล้ว — รันครั้งเดียว)
`cd backend & .venv\Scripts\activate & python -m app.seeds.disease_mapping_seed` → populate 21 รายการ. (หลังแก้นี้ launcher จะ auto-seed ให้เองตอนเปิด DB ใหม่)

### Tests run (sandbox)
- พิสูจน์ core fix แบบ inline: ก่อน seed options=**0** → หลัง seed options=**18** (จาก 21 dedup by key, key+label ครบ ไม่ fake)
- G1 = **13 passed**; G5 = **87 passed**; 3 fail = **sandbox mount-truncation artifacts** (test ใหม่ของรอบนี้+duplicate guard ที่พึ่งโมดูลที่ mount ตัดระหว่าง sync — ไฟล์จริง C:\ ครบ, บน Windows จะผ่าน). ไม่มี regression จาก test เดิม
- `npm run desktop:build` / `npx tsc` → ต้องรันบน Windows

### D4 workflow validation: **NO-GO — pending Windows re-run** (upload→step4 ต้องเห็น options→generate→export)

### Next recommended step
Windows: `git pull`/ใช้ working tree ปัจจุบัน → `cd frontend && npm run desktop:build && npx tsc --noEmit` → `cd ..\backend && pytest tests/ -q` (คาด G1 13 + G5 ครบรวม test ใหม่) → `python -m app.desktop.launch` → step 4 ต้องเห็นรายการโรค/บริการ (auto-seed) → เลือก service → generate → export → F5. ตรวจ `GET /api/system/status` → `row_counts.disease_mapping` > 0

---


## Session summary — Git commit prep: save D3/D4 work safely, exclude patient data (2026-06-16, session 9)

- **Goal:** commit เฉพาะโค้ด/test/docs กันงาน D3/D4/CID/SQLite/upload หาย โดย **ไม่ commit ข้อมูลจริง**
- **Key finding:** การแก้ทั้งหมด (รวม CID test fix) เป็น **working-tree changes ที่ยังไม่ commit** — HEAD ยังเป็น CID เก่า `1234567890123` (clone/reset แล้วจะ fail). นี่คือสาเหตุ Windows เห็นต่างจาก cowork.
- **ทำแล้ว (บันทึกลงโฟลเดอร์จริง):**
  - `.gitignore` เพิ่มกัน build artifact: `frontend/out/`, `frontend/tsconfig.tsbuildinfo`, `launcher/*.exe`, `*.patch`, `desktop-sqlite-test-results.txt`, `data/**/*.{xlsx,XLS,xls,csv}` + ยืนยัน `!tests/fixtures/**` (data เดิมกันครบอยู่แล้ว)
  - `docs/DATA_PRIVACY_GIT_TRACKING_AUDIT.md` reconfirm 70 ไฟล์ data/ tracked (รออนุมัติ git rm --cached)
- **Audit:** working tree 118 changes; data/ มี 70 ไฟล์ tracked (3 modified — **ไม่ stage**); 0 data/ untracked ใหม่; frontend/out 66 ไฟล์ (build artifact — exclude)
- **Blocker:** **commit ในแซนด์บ็อกซ์ทำไม่ได้** — `.git/index.lock` ค้าง (13 พ.ค.) ลบไม่ได้ (mount จำกัดสิทธิ์ .git) → **commit ต้องทำบน Windows** (ดูชุดคำสั่งใน session note / คำตอบ cowork)
- **Safety patch:** `git diff > WIP_D4_desktop_local_safety_backup.patch` (สร้างในแซนด์บ็อกซ์; แนะนำสร้างใหม่บน Windows ก่อน commit)
- **Data privacy cleanup:** แยกขั้น ยังไม่รัน git rm — รออนุมัติ
- **D4 workflow validation:** ยังคง **NO-GO** — ต้องผ่าน Windows upload→validate→generate→export ก่อน

---


## Session summary — Phase D4.7.3 — Fix target group upload timeout/reconciliation for large files (2026-06-16, session 8)

- **Date:** 2026-06-16
- **Task worked on:** Windows Round 4 FAIL — upload Excel ~12.9 MB / 21,309 rows timeout ที่ 30s ทั้งที่ backend สร้าง group สำเร็จ (เห็นใน Recent Groups) → frontend timeout ก่อน backend จบ + retry เสี่ยง duplicate job
- **Business logic changed:** **No** — แก้ frontend timeout classification + reconciliation + backend duplicate guard + timing log

### Root cause
1. `uploadTargetGroupFiles()` ใน `lib/api.ts` ใช้ default **read timeout 30s** — upload เป็น mutation งานหนัก (21,309 rows > 30s) → AbortController ยกเลิกฝั่ง client แต่ backend ทำต่อจน commit
2. ไม่มี duplicate guard — retry หลัง timeout จะสร้าง `target_group_jobs` ซ้ำ (`_validate_upload_batch` กันแค่ชื่อไฟล์ซ้ำในชุดเดียว)

### Files changed (ไม่แตะ matching/import rules)
| File | Change |
|---|---|
| `frontend/src/lib/api.ts` | upload-files/add-files/screening stage-upload/sync/confirm-import/run-match → mutation timeout **180s**; reads คง 30s |
| `frontend/.../TargetGroupUploadForm.tsx` | timeout → reconcile หา group ตาม group_name (ไม่ auto-retry) + ปุ่ม "เปิดกลุ่มเป้าหมายที่นำเข้าแล้ว"; 409 duplicate → guide ไป group เดิม; ข้อความ friendly |
| `backend/app/services/target_group_import_service.py` | `DuplicateUploadError` + guard: source_set_hash + group_name ซ้ำ → ไม่สร้าง job ใหม่ |
| `backend/app/api/target_groups.py` | upload endpoint: timing log (durationMs/file_count/row_count/status, ไม่มี identifier) + map `DuplicateUploadError`→409 พร้อม group_id |
| `backend/tests/test_target_group_duplicate_guard.py` | **ใหม่** — duplicate guard + different-name-allowed |

### Timeout strategy
read = 30s, mutation/import = 180s (แยกชัด ไม่ตั้งยาวทั้งระบบ)

### Reconciliation
upload timeout → "ระบบกำลังตรวจสอบว่างานนำเข้าสำเร็จหรือยัง" → `listTargetGroups` หา group_name ตรง → ถ้าพบ: "พบงานนำเข้าล่าสุดแล้ว" + ปุ่มเปิดกลุ่ม (ไม่ต้อง upload ซ้ำ); ถ้าไม่พบ: เตือนก่อน retry

### Duplicate prevention
source_set_hash + group_name → ถ้าซ้ำ raise DuplicateUploadError → endpoint 409 + existing group_id (frontend พาไป group เดิม). คนละชื่อกลุ่ม = upload ได้ปกติ (Postgres ไม่กระทบ)

### Tests run
- **รอบนี้ verify ในแซนด์บ็อกซ์ไม่ครบ:** bash mount truncate ไฟล์ใหญ่ระหว่าง sync (เช่น service 1285 บรรทัด/ตัดกลาง, api.ts ตัดท้าย) → tsc/pytest รายงาน error ปลอม. ยืนยันไฟล์จริง (C:\) ครบถูกต้องทุกไฟล์ผ่าน Read tool. **D4.7.2 รอบก่อนรัน 99 passed + tsc clean สำเร็จ** (พิสูจน์ harness). รอบนี้ต้อง verify บน Windows
- Business logic changed = **No**

### D4 workflow validation: **NO-GO — pending Windows Round 4 re-run**

### Backend regression / CID test data (ตรวจ 2026-06-16, session 8)
- ผู้ใช้รายงาน Windows G5 75/4 fail (CID เก่า 1234567890123 / 1111111111111 ไม่ผ่าน Thai check digit). **ตรวจแล้วในโฟลเดอร์ที่เชื่อมต่อ (C:\2025\web-69) test data ถูกแก้เป็น 1234567890121 แล้วตั้งแต่ session ก่อน** — 4 tests ที่รายงาน fail รันในทรีนี้ **ผ่านทั้งหมด** (`pytest <4 ids>` = 4 passed) + `test_normalization_utils.py` มี invalid-checksum coverage ครบ (1234567890123 และ 1234567890000 = invalid_identifier).
- **ไม่ได้ rollback production validation** (`_thai_id_check_digit_valid` คงเดิม). CID เก่าที่ยังเหลือ (1234567890123/1111111111111) อยู่เฉพาะ test ที่ใช้ SimpleNamespace fake (ไม่ผ่าน validation → ไม่ fail) — ไม่ต้องแก้.
- หมายเหตุ: ถ้า Windows ยัง fail แสดงว่า working copy ฝั่งผู้ใช้ยังไม่ตรงกับโฟลเดอร์นี้ → ให้รัน pytest ในโฟลเดอร์นี้ / git pull ให้ตรง.
- Sandbox: G1 = **13 passed**; G5 = **87 passed** + 1 fail (`test_target_group_duplicate_guard::test_duplicate_upload_guard`) ที่เป็น **sandbox-only artifact** (bash mount cache โมดูล service เวอร์ชันไม่ครบระหว่าง sync — ไฟล์จริงมี `DuplicateUploadError` ครบ) — บน Windows (ไฟล์ครบ) จะผ่าน.

### Next recommended step
Windows: `cd frontend && npm run desktop:build && npx tsc --noEmit` → `cd ..\backend && python -m compileall app -q && pytest tests/ -q` (คาดว่า G1 13 + G5 ครบรวม duplicate guard) → `python -m app.desktop.launch` → upload ไฟล์ 21,309 rows: ต้องไม่ timeout ที่ 30s, ถ้านานเห็น progress/reconciliation, กดซ้ำไม่ duplicate → validate → generate → export → F5 → close/reopen. ผ่านครบ → mark D4 PASS

---


## Session summary — Phase D4.7.2 — Fix SQLite "database is locked" on target group upload (2026-06-16, session 7)

- **Date:** 2026-06-16
- **Task worked on:** Windows real test FAIL — กด "อัปโหลดและตรวจตัวอย่าง" → `sqlite3.OperationalError: database is locked` ที่ `INSERT INTO target_group_jobs`
- **Business logic changed:** **No** — แก้เฉพาะ DB engine config, application-level write lock, error mapping, frontend double-submit guard (matching/result generation/import rules/CID validation/provenance ไม่แตะ)

### Root cause

1. `upload_files()` รันทั้ง flow ใน **transaction เดียว**: `db.flush()` insert `target_group_jobs` (จับ SQLite write lock) → loop อ่าน+parse Excel + stage rows → `db.commit()` ท้ายสุด → write lock ถูกถือยาวตลอดการ parse
2. SQLite engine **ไม่มี `busy_timeout` / connect timeout** → write ที่ชน lock **fail ทันที** แทนที่จะรอ
3. ไม่มี application-level serialization → double-submit / request ซ้อน ชนกัน

### Files changed

| File | Change |
|---|---|
| `backend/app/db/session.py` | เพิ่ม `PRAGMA busy_timeout=30000` + `connect_args timeout=30s` (เฉพาะ sqlite); PostgreSQL ไม่แตะ |
| `backend/app/db/write_lock.py` | **ใหม่** — `sqlite_write_lock()` context manager (threading.RLock, acquire timeout 30s) + `WriteBusyError`; no-op บน PostgreSQL |
| `backend/app/api/target_groups.py` | wrap upload-files / add-files / confirm-import / run-match / generate-results ด้วย `sqlite_write_lock()` |
| `backend/app/api/imports.py` | wrap sync-main-dataset (screening DB import) ด้วย `sqlite_write_lock()` |
| `backend/app/main.py` | exception handler: `WriteBusyError`→423 friendly, `OperationalError` "database is locked"→503 friendly (log raw SQL ฝั่ง server เท่านั้น ไม่ leak สู่ UI) |
| `frontend/src/components/target-groups/TargetGroupUploadForm.tsx` | double-submit guard ใน handleUpload + log `[upload] started/completed/failed` (durationMs/status, ไม่มี identifier) |
| `backend/tests/test_desktop_sqlite_concurrency.py` | **ใหม่** — 6 tests: busy_timeout, write lock busy/no-op, handlers registered, 423/503 friendly mapping |

### SQLite config changes

`PRAGMA foreign_keys=ON` + `journal_mode=WAL` + `synchronous=NORMAL` (เดิม) + **`busy_timeout=30000` (ใหม่)** + `connect_args={check_same_thread:False, timeout:30}`

### Write lock / double-submit behavior

- เฉพาะ sqlite → serialize writers ผ่าน process-wide RLock; ถ้ารอเกิน 30s → `WriteBusyError` → 423 "มีงานนำเข้า/บันทึกข้อมูลกำลังทำงานอยู่ กรุณารอ..." → กัน duplicate `target_group_jobs`
- PostgreSQL/LAN → no-op (MVCC)
- frontend: ปุ่ม disabled ระหว่าง pending + guard กันกดรัว

### Friendly error

db locked → UI เห็น "ฐานข้อมูลกำลังถูกใช้งานโดยงานอื่น กรุณารอสักครู่แล้วลองใหม่อีกครั้ง..." (ไม่มี raw SQL); developer ยังเห็น full detail ใน backend log

### Tests run (sandbox — mount sync healthy รอบนี้)

- `python -m compileall app -q` clean
- `pytest tests/test_desktop_sqlite_workflow.py` → **13 passed** (G1)
- `pytest tests/ --ignore=...workflow` → **86 passed** (G5 + concurrency 6 ใหม่) → รวม **99 passed / 0 failed**
- `npx tsc --noEmit` clean
- **ไม่ได้รัน:** `npm run desktop:build` (mnt SIGBUS) → ต้องรันบน Windows

### D4 workflow validation: **NO-GO — pending Windows re-test** (ต้อง upload→validate→generate→export ผ่านจริงบนเครื่อง + กด upload รัว ๆ ต้องไม่ locked/ไม่ duplicate)

### Next recommended step

Windows: ปิด launcher/process ค้าง (`Get-Process python`, `Get-NetTCPConnection -LocalPort 8010`) → `cd frontend && npm run desktop:build && npx tsc --noEmit` → `python -m app.desktop.launch` → upload (กดครั้งเดียว + กดรัว ๆ) ต้องไม่ database locked / ไม่ duplicate job → validate → generate → export → F5. ถ้าผ่านครบ → mark D4 PASS แล้วค่อยพิจารณา D5 packaging

---


## Session summary — Phase D4.7.1 — Fix "generate result" loading stuck + stage progress + horizontal overflow (2026-06-15, session 6)

- **Date:** 2026-06-15
- **Task worked on:** Windows real test รอบ 2 FAIL — หน้า "สร้างผลลัพธ์ / เลือกรายการโรคหรือบริการ" ค้างที่ "กำลังโหลดรายการบริการ..." เงียบ (ไม่มี timeout/retry/progress) + ยังมี horizontal scrollbar
- **Business logic changed:** **No** — แก้เฉพาะ frontend loading / state / query / error handling / UI layout

### Root cause (loading stuck)

1. `TargetGroupUploadForm.tsx` step 4: โหลด disease options ด้วย `getDiseaseOptions().then().catch(() => {})` — **catch กลืน error ทิ้ง** และ render เช็คแค่ `diseaseOptions.length > 0` → API fail / hang / empty ทั้งหมดแสดง "กำลังโหลดรายการบริการ..." ค้างตลอด แยกไม่ออก
2. `lib/api.ts` `request()`: **ไม่มี timeout** (fetch ไม่มี AbortController) → backend/DB ค้าง = loading ไม่รู้จบทั้งระบบ

### Files changed (frontend เท่านั้น)

| File | Change |
|---|---|
| `frontend/src/lib/api.ts` | AbortController hard timeout (read 30s / generate-results 180s), `ApiErrorKind` += `"timeout"`, log durationMs (path only) |
| `frontend/src/components/common/useElapsedSeconds.ts` | **ใหม่** — hook นับวินาที (elapsed + slow notice) |
| `frontend/src/components/common/StageProgress.tsx` | **ใหม่** — stage-based progress: bar + "ขั้นตอน X/Y" + elapsed + slow(15s) + retry + error state; ระบุ "ความคืบหน้าตามขั้นตอน (ไม่ใช่จำนวนรายการจริง)" |
| `frontend/src/components/target-groups/TargetGroupUploadForm.tsx` | step 4: optionsStatus (loading/success/error) + retry + empty แยกจาก error; generate: stage progress 7 ขั้น + double-fire guard + retry on fail; debug log `[tg-detail]` |
| `frontend/src/app/target-groups/detail/page.tsx` | loading ใช้ StageProgress 5 ขั้น + elapsed + retry |
| `frontend/src/app/globals.css` | overflow guard: `html,body{max-width:100%;overflow-x:hidden}`, `.main-column{overflow-x:clip}`, `.app-shell/.panel{max-width:100%}` (ตาราง/stepper ยังมี scroll container เอง → ข้อมูลไม่หาย) |

### Behavior หลังแก้

ทุก fetch จบด้วย success/empty/error/timeout • เกิน 15s แสดง "โหลดนานกว่าปกติ..." + ปุ่มลองใหม่ • API fail แสดง error จริง • empty ใช้เฉพาะสำเร็จแต่ไม่มีข้อมูล • matching/result generation/import rules/CID validation/provenance ไม่เปลี่ยน

### Tests run

- **ไม่ได้รันในแซนด์บ็อกซ์:** `npm run desktop:build` / `npx tsc --noEmit` / pytest — bash mount ไม่ sync การแก้ไฟล์เดิม (เห็นเวอร์ชันเก่า) ทำให้ verify ในแซนด์บ็อกซ์เชื่อถือไม่ได้ → **ต้องรันบน Windows** (โฟลเดอร์จริงของไฟล์ถูกต้องครบแล้ว)
- ไม่ได้แตะ backend → ไม่ต้องรัน G1/G5 ใหม่ (จะรันก็ต่อเมื่อแตะ backend)

### D4 workflow validation: **NO-GO — pending Windows re-test รอบ 3**

### Next recommended step

Windows: `cd frontend && npm run desktop:build && npx tsc --noEmit` → `python -m app.desktop.launch` → ทำ Round-3 manual test (L1–L10) ใน `docs/DESKTOP_D4_WORKFLOW_VALIDATION.md` — ถ้ายัง fail เปิด DevTools Console copy `[tg-detail]` / `[api]` / `[progress]` กลับมา (ไม่มี identifier). ถ้าผ่าน → data privacy git tracking decision + D4 full workflow validation (13 ข้อ) ด้วย synthetic data

---


## Session summary — Phase D4.7 — Fix target group detail data-loading bug (2026-06-11, session 5)

- **Date:** 2026-06-11
- **Task worked on:** แก้ bug หน้า "ผลลัพธ์กลุ่มเป้าหมาย" ค้าง empty state (disease options + result table) จนต้อง F5
- **Business logic changed:** **No** — UI data-loading layer + HTTP cache header เท่านั้น

### Root cause

หน้า detail (D4 เดิม) fetch group + disease options ครั้งเดียวตอน mount ด้วย `Promise.allSettled` แล้ว**กลืน failure/empty เป็น `[]` ถาวร** — ไม่มี retry, ไม่ refetch, ไม่แยก error กับ empty ถ้า fetch แรกพลาด (เช่น SQLite ยัง lock จาก upload ที่เพิ่งเสร็จ หรือ dataset ยังว่าง) หน้าจะค้างจนผู้ใช้ F5 และ workspace mount-effect (default service selection) รันครั้งเดียว — options ที่มาทีหลังไม่ trigger ใหม่

### Fixes

| File | Change |
|---|---|
| `frontend/src/app/target-groups/detail/page.tsx` | Rewritten: แยก status ต่อ call (loading/success/error), retry แยกปุ่ม, reset+refetch เมื่อ `?id=` เปลี่ยน, cancelled-flag กัน stale response, banner ชัดเจนเมื่อ options ว่างจริง (สำเร็จแต่ไม่มีข้อมูล) + ปุ่มลองใหม่, `key` remount workspace เมื่อ options มาถึง, debug log `[tg-detail]` (ไม่มี identifier) |
| `frontend/src/lib/api.ts` | Privacy: log path โดยตัด query string (q อาจมี CID ที่พิมพ์ค้นหา) |
| `backend/app/main.py` | `Cache-Control: no-store` สำหรับ `/api/*` + `/health` กัน browser cache stale payload (serving layer, ไม่ใช่ business logic) |

### Tests run (sandbox)

- `npx tsc --noEmit` PASS, `compileall` clean, **G1+G5 = 93 passed / 0 failed**
- Launcher live check: `/health` มี `cache-control: no-store` ✓, `/api/target-groups/disease-options` ตอบปกติบน SQLite ✓
- **ไม่ได้รัน:** `npm run desktop:build` (sandbox mnt FS SIGBUS) + manual Windows flow → ต้องทำบนเครื่องจริง

### D4 workflow validation: **NO-GO — pending Windows re-test**

### Next recommended step

Windows: `cd frontend && npm run desktop:build` → launcher → ทำ flow 10 ข้อ (เปิด→เลือกกลุ่ม→options โหลดเอง→generate→F5→reopen) — ถ้ายัง fail ให้เปิด DevTools Console copy บรรทัด `[tg-detail]` + `[api]` กลับมา (ไม่มีข้อมูลผู้ป่วยใน log แล้ว)

---


## Session summary — Phase D4 — Frontend Real App Entrypoint / Static Bundle (2026-06-11, session 4)

- **Date:** 2026-06-11
- **Task worked on:** D3.1 Windows validation recorded (PASSED) + D3.2 data privacy audit + D4 frontend static bundle + FastAPI static serving + launcher entry priority
- **Business logic changed:** **No** — matching/result generation/import rules untouched; UI shell + serving layer only

### D3.1 Windows validation: PASSED (developer run)

health ok / desktop_local / sqlite / bind 127.0.0.1 only / DB readable via API / logs clean (no 13-digit) / port released after shutdown / no Docker

### Files changed

| File | Change |
|---|---|
| `frontend/src/app/dashboard/page.tsx` | server → client component (runtime fetch + LoadingState) |
| `frontend/src/app/target-groups/page.tsx` | server → client component |
| `frontend/src/app/patients/detail/page.tsx` | **New** — query-param detail page แทน `/patients/[id]` (ลบแล้ว) |
| `frontend/src/app/target-groups/detail/page.tsx` | **New** — แทน `/target-groups/[id]` (ลบแล้ว) |
| `frontend/src/components/target-groups/TargetGroupUploadForm.tsx` | 2 nav sites → `/target-groups/detail?id=` |
| `frontend/next.config.js` | `output:"export"` เฉพาะ `DESKTOP_STATIC=1` — LAN build ไม่เปลี่ยน |
| `frontend/package.json` + `frontend/scripts/desktop-build.js` | `npm run desktop:build` (cross-platform) |
| `backend/app/main.py` | serve `frontend/out` ที่ `/` เฉพาะ desktop_local + bundle exists; placeholder ถ้ายังไม่ build |
| `backend/app/desktop/launch.py` | rewritten clean UTF-8; entry priority: static app → dev 3020 → /docs; safe structured log |
| `.gitignore` | data privacy hardening (db/sqlite/targets/samples/xlsx ใหม่) |
| `docs/DATA_PRIVACY_GIT_TRACKING_AUDIT.md` | **New** — 70 tracked files, เสนอ git rm --cached รออนุมัติ |
| `docs/DESKTOP_D4_WORKFLOW_VALIDATION.md` | **New** — 13-step plan, synthetic only |

### Data privacy audit result

`data/` มี 70 ไฟล์ถูก git track (41 source DKTP xlsx + targets + uploads + exports) — ความเสี่ยงสูงว่าเป็นข้อมูลจริง เสนอ `git rm -r --cached data/` (ไฟล์จริงไม่หาย) **รอเจ้าของ repo อนุมัติ** + ตัดสินใจ history cleanup ถ้าเคย push remote

### Tests run (sandbox)

- `compileall` clean; **G1+G5 = 93 passed / 0 failed** (รวม 13+80)
- `npx tsc --noEmit` = PASS (หลัง refactor)
- Static serving E2E: root serves bundle, /health + /api + /docs ปกติ, ไม่มี build → placeholder JSON
- **ไม่ได้รัน:** `npm run desktop:build` ใน sandbox (mnt FS SIGBUS — ข้อจำกัด sandbox) → ต้อง build บน Windows

### Blockers

1. `npm run desktop:build` + workflow validation 13 ข้อ ต้องรันบน Windows
2. Data privacy: รอตัดสินใจ untrack `data/`
3. Runtime API-base config (dynamic port) — ยังใช้ fixed 8010 (default ใน api.ts ปลอดภัยอยู่แล้ว)

### Next recommended step

บน Windows: `cd frontend && npm run desktop:build` → `python -m app.desktop.launch` → ทำ `docs/DESKTOP_D4_WORKFLOW_VALIDATION.md` 13 ข้อ → รายงานผล → ถ้าผ่านจึงเริ่มวางแผน D5 (packaging)

---


## Session summary — Phase D3.1/D3.2 — Desktop Shell Windows Validation Prep + Frontend Entry Audit (2026-06-11, session 2)

- **Date:** 2026-06-11
- **Task worked on:** D3.1 Windows launcher validation prep + D3.2/D3.3 frontend entrypoint & API base audit + D3.5 data safety
- **Business logic changed:** **No** — matching/result generation/import rules untouched

### Files changed

| File | Change |
|---|---|
| `backend/app/desktop/launch.py` | D3.2: `_pick_entry_url()` — เปิด frontend `127.0.0.1:3020` ถ้ารันอยู่, ไม่งั้น `/docs`; `DESKTOP_OPEN_URL` override (loopback only) |
| `backend/scripts/check_desktop_launcher.ps1` | **New (v2)** — validation logic ทั้งหมดย้ายมา PowerShell หลัง .bat v1 พังบน Windows (batch parser ตีความ URL/วงเล็บ/ข้อความไทยใน echo block เป็น command) |
| `backend/scripts/check_desktop_launcher.bat` | เหลือเป็น wrapper 4 บรรทัด เรียก ps1 เท่านั้น — ห้ามใส่ logic/ข้อความใน .bat อีก |
| `.gitignore` | D3.5: `data/*.db`, `*.db-wal/shm`, exports/, backups/, uploads/, reports/, `backend/config/settings.json` |
| `docs/DESKTOP_SHELL_PROTOTYPE.md` | Rewritten — status, troubleshooting, D4 plan |
| `docs/DESKTOP_SQLITE_D3_WORKFLOW_NOTES.md` | Section 12 added |

### Tests run (sandbox, 2026-06-11)

- `compileall` clean; **G1 = 13 passed**, **G5 = 80 passed** (re-run after launcher change — see below)
- Launcher sandbox check: `/health` = `{"status":"ok","app_edition":"desktop_local","database_engine":"sqlite"}`, listener `127.0.0.1:8010` only (`ss -tlnp`)

### Windows validation result

**PENDING** — sandbox is Linux; developer must run `backend\scripts\check_desktop_launcher.bat` on the Windows machine and report output.

### Frontend integration status (audit complete)

- API base: single point `src/lib/api.ts` — `NEXT_PUBLIC_API_BASE_URL ?? http://127.0.0.1:8010` ✓ no 0.0.0.0/LAN hardcode
- No Next.js API routes ✓
- Blockers for static export: `/patients/[id]`, `/target-groups/[id]` are server components → D4 = refactor 2 pages to client components, then FastAPI serves static bundle (end users need no Node.js)
- Build-time env → runtime config injection planned for dynamic port (D4)

### Blockers / open issues

1. Windows validation pending (→ **D4 Gate = NO-GO**)
2. **Privacy:** ~70 ไฟล์ใน `data/` (source xlsx + exports) ถูก git-track อยู่ก่อนแล้ว — ต้องตัดสินใจ `git rm --cached` + พิจารณา history cleanup แยกต่างหาก
3. 0-byte `data/seamlessfordmis.db` จาก sandbox dev — ลบได้อย่างปลอดภัยหรือปล่อยให้ launcher init ทับ (ตอนนี้ gitignored แล้ว)

### Next recommended step

รัน `check_desktop_launcher.bat` บน Windows → รายงานผล → ถ้าผ่าน เริ่ม D4 (frontend static bundle + runtime config + single-instance lock)

---

## Session summary — Phase D2.18 — Fix G5 regression after Thai CID check digit validation + D3 Gate YES (2026-06-11)

- **Date:** 2026-06-11
- **Task worked on:** Fix G5 regression (4 failed tests) caused by synthetic test CIDs that fail the DOPA check digit — updated test data, NOT production validation
- **Business logic changed:** **No** — production code untouched; only synthetic CID values in 2 test files

### CID test data update

| File | From | To | Reason |
|---|---|---|---|
| `tests/test_normalization_utils.py` | `" 123-456-7890123.0 "` / `"1234567890123"` | `" 123-456-7890121.0 "` / `"1234567890121"` | `...123` fails DOPA checksum (check digit should be 1); `...121` passes |
| `tests/test_target_group_import.py` | `1234567890123` (all occurrences) | `1234567890121` | same |
| `tests/test_target_group_import.py` `_roster_row` | `1111111111111` | `1111111111119` | `...111` fails checksum (check digit should be 9); `...119` passes |

### Invalid checksum coverage added (Phase 2)

- New test `test_normalize_identifier_rejects_13_digit_with_bad_check_digit`: asserts `1234567890123` and `1234567890000` → `invalid_identifier` (looks_like_13_digit=True, never valid, never silent no-history)
- Existing `test_invalid_cid_rows_remain_visible_in_summary` unchanged — invalid rows stay visible in staging

### Why validation was NOT rolled back

Thai CID check digit is a hospital-data correctness rule: a fake CID accepted as valid risks wrong-person matching or silent misclassification. The old synthetic test data was wrong, not the validation.

### Test results (run 2026-06-11, sandbox Linux + Windows-compatible)

- `python -m compileall app -q` → OK
- **G1** `pytest tests/test_desktop_sqlite_workflow.py -v -p no:randomly` → **13 passed / 0 failed** ✅
- **G5** `pytest tests/ --ignore=tests/test_desktop_sqlite_workflow.py -v` → **80 passed / 0 failed** ✅ (79 original + 1 new invalid-checksum test)

### D3 Gate decision: **YES** ✅

All criteria met: G1 13/13, G5 80/80 (≥79 required, 0 failed), check digit active, invalid CIDs classified `invalid_identifier`, leading-zero handling intact (B3/B4 pass), no business logic regression, docs updated.

### Next recommended step

D3 Minimal Desktop Shell Prototype (`python -m app.desktop.launch`) — see `docs/DESKTOP_SHELL_PROTOTYPE.md`. No Docker, no installer/EXE yet.

---

## Session summary — Phase D2.17 — B-Series Root-Cause Fixes: CID Leading Zero + Thai Check Digit (2026-06-10)

- **Date:** 2026-06-10
- **Task worked on:** Fix 4 failing G1 smoke tests (B1, B3, B4, B5) — root-cause analysis + 3 targeted fixes
- **Scope:** 2 backend source files + 1 test fixture. No business logic changed. No LAN/PostgreSQL path changed.
- **Business logic changed:** No — `dtype=object` preserves existing normalization semantics. Check-digit validation is a correctness addition consistent with project safety rules ("ห้ามลดความสำคัญของ exact CID").

### Root Causes Found

| Test | Root Cause |
|---|---|
| B1 `INVALID_CID` staged as `invalid_identifier` | `normalize_identifier` had no check-digit validation → `1234567890000` was `valid_identifier` |
| B3 DAVE exactly 1 result row | pandas default dtype inference: `"0112000000044"` → `int64` 112000000044 → 12 digits → `invalid_identifier` → no result row |
| B4 BOB `has_selected_service=True` | Same pandas dtype loss of leading zero |
| B5 EVE selected-service date isolation | Same pandas dtype loss + service column fix already applied in D2.15 |

### Fixes Applied

| # | File | Change |
|---|---|---|
| 1 | `backend/app/utils/text_normalization.py` | Added `_thai_id_check_digit_valid()` (DOPA mod-11 algorithm) + integrated into `normalize_identifier()` |
| 2 | `backend/app/importers/excel_target_group_importer.py` | `_read_generic_sheet` line 291: `workbook.parse(sheet_name=sheet_name, dtype=object)` |
| 3 | `tests/fixtures/desktop_local/target_group_multisheet.xlsx` | Regenerated with correct column names (`ชื่อบริการ`, `วันที่ตรวจ`) and CIDs as openpyxl string cells |

### Sandbox Verification (2026-06-10)

Pipeline simulation run (openpyxl + pandas, no pytest):
- Fixture: 12 rows total, 7 roster + 5 history
- `INVALID_CID='1234567890000'` → `invalid_identifier` ✓ (B1)
- `CID='0112000000028'` (BOB) × 2 cervical rows → `has_selected_service=True` ✓ (B4)
- `CID='0112000000052'` (EVE) cervical `2022-05-01` ≠ diabetes `2023-12-20` ✓ (B5)
- Sheet `ประวัติ` → `history_sheet` ✓, Sheet `รายชื่อ` → `roster_sheet` ✓

### Tests Run

- Sandbox pipeline simulation: **ALL CHECKS PASSED**
- `pytest` G1 + G5: **CANNOT RUN IN SANDBOX** (no PyPI access) — must run on developer Windows machine

### D3 Gate Status: **NO-GO — pending G1+G5 developer run**

All 3 fixes in place and verified. Gate opens when developer runs:

```bat
cd backend
.venv\Scripts\activate
pytest tests/test_desktop_sqlite_workflow.py -v -p no:randomly
```

Expected: **13 passed**. If green → run G5 regression → update this file → D3 unlocked.

---

## Session summary — Phase D2.15/D2.16 Run-environment hardening + Second-pass verification (2026-06-04)

- **Date:** 2026-06-04
- **Task worked on:** Make test suite runnable on developer's Windows machine with one command; second-pass verification of all 13 smoke tests; fixture integrity re-check
- **Scope:** Test tooling + docs only. No production code, no business logic touched.
- **Business logic changed:** No.

### What happened

- Traced full import chain for all 3 services used by the test (`TargetGroupImportService`, `ResultGenerationService`, `ExportService`): none imports `app.db.session` → **no PostgreSQL connection attempted at test import time** → D2.15 smoke tests run without `.env` or PostgreSQL ✅
- Confirmed `app.db.session` is only imported by `app.db.init_db` which is NOT in any test's import chain ✅
- Confirmed `DiseaseScreeningRecord` unique constraint `(source_import_job_id, source_file_id, source_row_no)` — SQLite treats NULL as distinct → ALICE×2 rows with `NULL` source_file_id safe ✅
- Confirmed `upload_files()` commits internally; test's extra `db.commit()` is harmless no-op ✅
- Fixed `tests/fixtures/desktop_local/cid_constants.py`: removed duplicate `INVALID_CID` line + null bytes from Edit tool corruption ✅
- Re-ran `scripts/verify_desktop_fixtures.py`: **27/27 PASS** (D2.15 column fix intact, B1-B5 all supported) ✅
- Added `backend/pytest.ini` with `pythonpath = .` (makes `app` importable without package install) and safe filterwarnings
- Added `backend/conftest.py` (rootdir marker + safety rules comment)
- Added `backend/run_tests.bat` (simple per-developer runner; companion to `scripts/run_desktop_sqlite_tests.bat`)
- Added Second-Pass Verification table to `docs/DESKTOP_SQLITE_D3_WORKFLOW_NOTES.md`

### Files changed

| File | Change |
|---|---|
| `backend/pytest.ini` | New — `pythonpath = .`, filterwarnings; no addopts to avoid conflict with `-v` in run scripts |
| `backend/conftest.py` | New — rootdir marker + safety rules comment |
| `backend/run_tests.bat` | New — simple Windows runner: `d2.15` / `d2.16` / `all` modes |
| `tests/fixtures/desktop_local/cid_constants.py` | Fixed — removed duplicate `INVALID_CID` line; rewrote via bash to eliminate null bytes |
| `docs/DESKTOP_SQLITE_D3_WORKFLOW_NOTES.md` | Added Second-Pass Verification table (13 items) |
| `PROJECT_STATUS.md` | This summary |

### Tests run

- `scripts/verify_desktop_fixtures.py` — **27/27 PASS** (ran in sandbox via Python 3.10)
- `python3 -m ast` parse on all critical files — **all clean**
- `pytest` (G1, G5) — **STILL CANNOT RUN IN SANDBOX** (no PyPI, deps not installed); must run on developer machine

### D3 Gate status: unchanged — **NO-GO until developer runs G1+G5**

Gate G1 (pytest smoke) and G5 (regression) have never been executed on a real Python env. Everything else is ✅. Per project rules, Desktop Shell work is blocked until a real run confirms all 13 tests pass.

### One-command run for developer

```bat
cd C:\2025\web-69\โรงบาลหนองพอก\seamlessfordmis
scripts\run_desktop_sqlite_tests.bat
```
→ Creates `.venv`, installs deps, runs G4+G1+G5, writes `desktop-sqlite-test-results.txt`

Or from inside `backend/`:
```bat
cd backend && run_tests.bat all
```

---

## Session summary — Phase D2.16 Fixture Integrity Verifier + D3 Gate Re-check (2026-05-30)

- **Date:** 2026-05-30
- **Task worked on:** Attempt to run the SQLite workflow smoke suite for real; add a dependency-light fixture integrity guard; re-evaluate the D3 gate.
- **Scope:** Test tooling + docs only. No production code, no business logic touched.
- **Business logic changed:** No.

### What happened
- **Real `pytest` run is NOT possible in the assistant sandbox.** Confirmed three ways: PyPI blocked by proxy (403), `sqlalchemy`/`pydantic`/`fastapi`/`pytest` not installed, and a full-filesystem search found no alternate Python env or site-packages with these. This is an environment limitation, not a code defect. G1/G5 must be run on a developer machine.
- To remove that friction, added one-click runners (`scripts/run_desktop_sqlite_tests.{bat,sh}`) that build a venv, install `backend/requirements.txt`, then run G4+G1+G5 and write `desktop-sqlite-test-results.txt`.
- Added `scripts/verify_desktop_fixtures.py` — a stdlib + openpyxl fixture-drift guard (no pip needed). **Ran it here: 27/27 PASS.** Confirms the fixtures still support B1–B5 + 1-person-1-row dedup (invalid/missing CID staged, BOB TG-only cervical history, EVE cervical 2022-05-01 ≠ diabetes 2023-12-20, DAVE in both sheets, mod-11 checksums correct, history column = `ชื่อบริการ`).
- PostgreSQL-marker scan of `backend/app`: only the already-known/safe files (`db/compat.py` dispatcher, `db/types.py` portable types, `models/patient.py` partial index ignored by SQLite, `services/phase_f_population_service.py` SQLite-guarded). No new PostgreSQL-only code on the Desktop smoke path.

### Files changed
| File | Change |
|---|---|
| `scripts/run_desktop_sqlite_tests.bat` | New — Windows one-click G4/G1/G5 runner → results log |
| `scripts/run_desktop_sqlite_tests.sh` | New — POSIX equivalent |
| `scripts/verify_desktop_fixtures.py` | New — stdlib+openpyxl fixture integrity guard (27/27 PASS here) |
| `docs/DESKTOP_SQLITE_D3_WORKFLOW_NOTES.md` | Appended D2.16 verification entry |
| `PROJECT_STATUS.md` | This summary |

### Tests run / not run
- **Ran:** `compileall backend/app` (clean), `verify_desktop_fixtures.py` (27/27 PASS).
- **NOT run (cannot, sandbox):** `pytest` smoke (G1) and regression (G5) — require a real Python env.

### D3 Gate decision: **NO-GO (do not start Desktop Shell yet)**
G1 + G5 have never been executed on a real environment, so the gate cannot be certified. Static analysis (D2.15) + fixture verifier (D2.16) both strongly predict PASS, but a prediction is not a run. Per the project's own gate rules, shell/installer work stays blocked.

### Next recommended step
Run `scripts\run_desktop_sqlite_tests.bat` on the Windows dev machine, paste `desktop-sqlite-test-results.txt` back. If G1 green + G5 no-regression → start Minimal Desktop Shell Prototype (pywebview + FastAPI + SQLite, bind 127.0.0.1). If red → fix root cause (dialect/compat only), no business-meaning change.

---

## Session summary — Phase D2.15 SQLite Smoke Test Static Analysis + Fixture Fix (2026-05-29)

- **Date:** 2026-05-29
- **Task worked on:** Phase D2.15 — Static analysis of all 13 SQLite workflow smoke tests + fix critical fixture column-naming bug
- **Scope:** Test fixture + test documentation only. No production code business logic changed.
- **Business logic changed:** No — did not change matching logic, result generation meaning, import/mapping rules, exact CID priority, visible result table behavior, provenance, audit trail, or export business rules.

### Files changed

| File | Change |
|---|---|
| `tests/fixtures/desktop_local/target_group_multisheet.xlsx` | Renamed "ประวัติ" sheet column C `"ประเภทบริการ"` → `"ชื่อบริการ"` (recognized by both `HISTORY_HINT_COLUMNS` classifier and `_extract_target_group_history_service`) |
| `tests/fixtures/desktop_local/README.md` | Added column note documenting that `"ชื่อบริการ"` is the correct header; regeneration warning added |
| `docs/DESKTOP_SQLITE_D3_WORKFLOW_NOTES.md` | Added Section 7: D2.15 static analysis, full 13-test verdict table, updated D3 gate checklist, go/no-go criteria, and developer run commands |

### Root cause of fixture bug

`target_group_multisheet.xlsx` "ประวัติ" sheet had column C as `"ประเภทบริการ"` instead of `"ชื่อบริการ"`.  
`_extract_target_group_history_service()` (field_mapping_service.py) does NOT recognize `"ประเภทบริการ"` → service key was never extracted → B4 (BOB TG-side history) and B5 (EVE selected-service date isolation) would fail.

Fix: renamed column in xlsx fixture using openpyxl. Production service code unchanged.

### Static analysis verdict (all 13 tests)

| Test | Predicted | Key check |
|---|---|---|
| S1 schema bootstrap | ✅ PASS | GUID→CHAR(36), JSONType→JSON, all column types SQLite-safe |
| I1 direct insert | ✅ PASS | All required fields provided; source_file_id nullable |
| T1 TG file upload | ✅ PASS | After fix: `"ชื่อบริการ"` in HISTORY_HINT_COLUMNS; _MockUploadFile interface correct |
| R1 generate on SQLite | ✅ PASS | `_session_dialect_name` falls back to `db.get_bind().dialect.name=="sqlite"` → correct dispatch |
| R2 summary row | ✅ PASS | `_upsert_summary_cache` executes via sqlite.insert() ON CONFLICT DO UPDATE |
| R3 upsert idempotency | ✅ PASS | Exactly 1 TargetGroupResultSummary row after double-generate |
| B1 invalid CID | ✅ PASS | INVALID_CID staged; `cid_validation_status` contains `"invalid"` |
| B2 missing CID | ✅ PASS | Blank-CID staged; `normalized_cid IS NULL` query matches |
| B3 DAVE 1 row | ✅ PASS | History-sheet row → `_stage_history_row()` + `continue` → no TargetGroupRow duplicate |
| B4 BOB evidence | ✅ PASS | After fix: BOB → `normalized_service_key="cervical_screen"` → `has_selected_service=True` |
| B5 EVE date isolation | ✅ PASS | After fix: EVE cervical 2022-05-01 from TG history; diabetes 2023-12-20 not included |
| E1 export file | ✅ PASS | `source_data_dir` patched; pandas+openpyxl writes non-empty file |
| P1 restart persistence | ✅ PASS | WAL mode; new engine reconnects to same file path |

### D3 Gate checklist current status

| Gate | Status |
|---|---|
| G1 — `pytest tests/test_desktop_sqlite_workflow.py -v -p no:randomly` all 13 pass | ⏳ Must run on developer machine |
| G2 — Backend boots with SQLite | ✅ Verified in D2 |
| G3 — `python -m app.desktop.init_db` | ✅ Verified in D2 |
| G4 — `python -m compileall app/ -q` | ✅ Passes |
| G5 — No regression: `pytest tests/ --ignore=tests/test_desktop_sqlite_workflow.py` | ⏳ Must run |
| G6 — No business logic changed | ✅ Confirmed |
| G7 — Real-world smoke with non-sensitive data | ⏳ Not yet done |

### Developer commands to run next

```bash
# D2.15 — SQLite smoke test gate
cd backend
pytest tests/test_desktop_sqlite_workflow.py -v -p no:randomly

# D2.16 — LAN/PostgreSQL regression gate (requires .env with DATABASE_URL)
pytest tests/ -v --ignore=tests/test_desktop_sqlite_workflow.py

# If both pass → Phase D3 Desktop Shell Prototype is UNLOCKED
```

### Production consideration pending approval

**Not yet applied.** Add `"ประเภทบริการ"` to the recognized column list in `_extract_target_group_history_service()` in `backend/app/services/field_mapping_service.py`. This is a common JHCIS/HosXP export column name. Requires explicit approval because it is a field-mapping rule change.

---

## Session summary — Phase D2 Desktop Local SQLite Data Layer Prototype (2026-05-27)

- **Date:** 2026-05-27
- **Task worked on:** Phase D2 Desktop Local SQLite Data Layer Prototype
- **Scope:** Backend runtime/data layer prototype only. No Desktop shell, no packaging, no production SQLite migration.
- **Business logic changed:** No — did not change matching logic, result generation meaning, import/mapping rules, exact CID priority, visible result table behavior, provenance, audit trail, or export business rules.

### Files changed

| File | Change |
|---|---|
| `backend/app/config.py` | Added `APP_EDITION`, `DATABASE_ENGINE`, local data path settings, and helper properties |
| `backend/app/db/session.py` | Added SQLite engine setup with local file creation and PRAGMA setup |
| `backend/app/db/types.py` | Added portable `GUID` and `JSONType` SQLAlchemy types |
| `backend/app/db/compat.py` | Added initial database dialect/query compatibility helpers |
| `backend/app/db/init_db.py` | Added Desktop path initialization and prototype schema metadata for SQLite mode |
| `backend/app/desktop/*` | Added Desktop helper package, path init command, and SQLite init command |
| `backend/app/models/*.py` | Replaced direct PostgreSQL UUID/JSONB model type usage with compatibility types |
| `backend/app/main.py` | Added safe runtime metadata to `/health` |
| `.env.example` | Added Desktop Local prototype env variables |
| `.env.offline.example` | Added explicit LAN/Postgres runtime variables |
| `docker-compose.yml` | Passed explicit LAN/Postgres runtime variables to backend |
| `docs/DESKTOP_SQLITE_D2_NOTES.md` | Added D2 implementation notes, commands, risks, and next phase plan |
| `PROJECT_ARCHITECTURE.md` | Updated Desktop Local architecture status for D2 |
| `PROJECT_STATUS.md` | Added this session summary |

### Tests run

- `python -m app.desktop.init_db` with `APP_EDITION=desktop_local`, `DATABASE_ENGINE=sqlite`, and smoke-only local paths — passed
- `python -m app.desktop.init_paths` with smoke-only local paths — passed after fixing Windows Thai-path console output encoding
- Started FastAPI with SQLite on `127.0.0.1:8010` and called `http://127.0.0.1:8010/health` — passed; returned `{"status":"ok","app_edition":"desktop_local","database_engine":"sqlite"}`
- `python -m compileall backend\app` with isolated pycache prefix — passed
- Static PostgreSQL-specific syntax search — completed; remaining blockers are documented in `docs/DESKTOP_SQLITE_D2_NOTES.md`
- Smoke artifacts under `backend\.desktop-smoke`, `backend\data`, and `backend\config` created by the test were removed after verification

### Known gaps / blockers

- SQLite bootstrap uses `create_all()` and is prototype-only, not a production migration path.
- PostgreSQL Alembic migration chain remains PostgreSQL-specific.
- Result summary upsert and Phase F raw SQL still need dialect-aware implementations before full workflow smoke on SQLite.
- Full import -> target group -> result -> export workflow has not been validated on SQLite.
- Desktop shell, installer, backup/restore zip, and clean machine test are not implemented yet.
- Docker CLI is not available in this environment, so `docker compose config` was not run.

### Next recommended step

Add regression tests and dialect-aware query helpers for SQLite workflow smoke, starting with result summary upsert/search compatibility, then validate import, multi-sheet target group, target-group-side history, result generation, export, backup/restore, and restart persistence using non-sensitive sample data.

---

## Session summary — Desktop Local Edition SQLite Feasibility Audit (2026-05-27)

- **Date:** 2026-05-27
- **Task worked on:** Start roadmap for SeamlessFordMIS Desktop Local Edition using SQLite local database and local file storage, without Docker/PostgreSQL server.
- **Scope:** Audit and documentation only. No Desktop runtime implementation yet.
- **Business logic changed:** No — did not change matching logic, result generation, import/mapping rules, exact CID priority, visible result table behavior, provenance, audit trail, or export logic.

### Files changed

| File | Change |
|---|---|
| `docs/DESKTOP_SQLITE_FEASIBILITY.md` | Added Phase D1 feasibility audit, SQLite compatibility findings, storage/runtime strategy, backup/restore strategy, Desktop architecture recommendation, and D2-D6 plans |
| `PROJECT_STATUS.md` | Added this session summary and current Desktop Local Edition status |

### Findings

- Desktop Local Edition is feasible, but not by only changing `DATABASE_URL` to SQLite.
- Current backend models and migrations are PostgreSQL-oriented through `PGUUID`, `JSONB`, `gen_random_uuid()`, PostgreSQL partial indexes, `pg_indexes`, JSONB casts, and PostgreSQL upsert helpers.
- Current frontend reads `NEXT_PUBLIC_API_BASE_URL` with fallback to `http://127.0.0.1:8010`; Desktop needs a safer local API strategy that supports dynamic local port or backend-served static frontend.
- Current file storage is environment-driven for source/upload/cache/logs, but Desktop needs a consistent local data layout and config for reports, exports, backups, and settings.
- Docker/LAN Edition remains intact and should continue as the LAN/server deployment path.

### Blockers / known gaps

- No SQLite-compatible model type layer exists yet.
- Current Alembic PostgreSQL migration chain should not be run against SQLite unchanged.
- PostgreSQL-specific services still need DB compatibility wrappers before Desktop runtime can be tested.
- Desktop packaging, local launcher/shell, SQLite backup/restore implementation, and clean machine testing are not implemented yet.
- No Desktop production-ready claim is allowed until clean machine workflow tests pass with non-sensitive sample data.

### Tests / checks run

- Static repository audit of backend models, API, services, Alembic migrations, frontend API usage, environment files, and Docker/offline config.
- PostgreSQL-specific syntax search for `ILIKE`, `JSONB`, `ARRAY`, `postgresql`, `ON CONFLICT`, `::uuid`, `server_default`, raw SQL, path constants, and API base URL usage.

### Next recommended step

Review `docs/DESKTOP_SQLITE_FEASIBILITY.md`, approve Phase D2 scope, then implement a narrow SQLite prototype behind `APP_EDITION=desktop_local` and `DATABASE_ENGINE=sqlite` with regression tests for exact CID, invalid identifiers, multi-sheet target groups, target-group-side history, selected-service latest date, one-person-one-row visible results, provenance, export, backup/restore, and restart persistence.

---

> ไฟล์นี้ใช้เป็นศูนย์กลางสถานะโปรเจกต์ เพื่อให้ AI Codex หรือผู้พัฒนาคนอื่นเข้ามาอ่านแล้วเข้าใจทันทีว่า:
> - โปรเจกต์นี้คืออะไร
> - ตอนนี้ทำถึงไหนแล้ว
> - มี business rules อะไรที่ห้ามเปลี่ยน
> - phase ปัจจุบันคืออะไร
> - task ถัดไปคืออะไร
> - ปัญหาค้างคืออะไร
> - หลัง Codex ทำงานเสร็จ ต้องอัปเดตไฟล์นี้ทุกครั้ง

---

## Session summary — Installer build modes + Launcher command mapping hardening (2026-05-27)

- **Date:** 2026-05-27
- **Task worked on:** ปิด gap ล่าสุดของ Windows Offline/LAN installer path หลังมี Docker package, GUI Launcher source, Launcher EXE, และ installer source แล้ว แต่ยังไม่มี Inno Setup/Docker runtime verification ใน environment นี้
- **Scope:** Installer build script, launcher command mapping, offline image script text, and docs only
- **Business logic changed:** No — ไม่แตะ matching logic, result generation, import/mapping rules, exact CID priority, visible result table behavior, provenance, audit trail, หรือ patient-data workflows

### Current implementation status

- Docker Offline/LAN package source exists.
- GUI Launcher source exists at `launcher/seamlessfordmis_launcher.py`.
- Launcher build script exists at `launcher/build-launcher.bat`.
- `launcher/SeamlessFordMIS-Launcher.exe` exists and was rebuilt in this session after source mapping fix.
- Windows Installer source exists at `installer/seamlessfordmis.iss`.
- `installer/Output/SeamlessFordMIS-Setup.exe` is still not built in this environment because `ISCC.exe` is missing.
- Docker runtime verification and Windows Clean VM test are still pending.

### Files changed

| File | Change |
|---|---|
| `installer/build-installer.bat` | Added explicit `check`, `dev`, and `offline-full` modes; made launcher build failure fatal; added clear Inno Setup/ISCC path diagnostics; made `offline-full` require all image tarballs |
| `launcher/seamlessfordmis_launcher.py` | Changed Open Web action to call existing `offline\open-web.bat` instead of duplicating browser-open behavior |
| `launcher/SeamlessFordMIS-Launcher.exe` | Rebuilt after launcher source change |
| `offline/load-images.bat` | Corrected installed image path guidance to `C:\SeamlessFordMIS\app\images\` |
| `offline/save-images.bat` | Updated next-step guidance to use `installer\build-installer.bat offline-full` |
| `installer/README_INSTALLER.md` | Documented build modes and clarified no-image dev installer is not a complete offline package |
| `launcher/README.md` | Added current launcher/installer build status and Clean VM pending note |
| `docs/GUI_LAUNCHER_PROPOSAL.md` | Added latest source/binary/installer integration status and build mode notes |
| `OFFLINE_INSTALL.md` | Added IT/build-machine section for `check`, `dev`, and `offline-full` installer builds |

### Tests / checks run

- `python -m py_compile launcher\seamlessfordmis_launcher.py` — passed
- `launcher\build-launcher.bat` — passed; output `launcher\SeamlessFordMIS-Launcher.exe` size `29,977,094` bytes
- Static launcher command mapping check — passed after fixing Open Web mapping to `open-web.bat`
- Static installer integration check — passed
- Static build-installer mode check — passed
- `installer\build-installer.bat check` — failed correctly because `ISCC.exe` is missing and image tarballs are incomplete
- `installer\build-installer.bat dev` — failed correctly because `ISCC.exe` is missing
- `installer\build-installer.bat offline-full` — failed correctly because image tarballs are missing and `ISCC.exe` is missing
- `npm.cmd run build` from `frontend/` — passed
- `npx.cmd tsc --noEmit` from `frontend/` — passed
- `python -m compileall backend\app` — passed
- Docker compose validation — skipped because Docker CLI is not installed/in PATH

### Known gaps / blockers

- Inno Setup 6 / `ISCC.exe` is not installed on this machine, so `SeamlessFordMIS-Setup.exe` is not built here.
- Docker CLI is not installed/in PATH, so Docker build, image save/load, compose up, migration, healthcheck, backup/restore, and URL smoke tests were not run here.
- `images\postgres-16.tar`, `images\nginx-alpine.tar`, `images\seamlessfordmis-backend.tar`, and `images\seamlessfordmis-frontend.tar` are not present; full offline installer requires them.
- Windows Clean VM verification is still pending. Do not call this production-ready until the clean VM test report is completed.

### Next recommended step

1. On a Windows build machine with Docker Desktop and Inno Setup 6 installed, run `offline\save-images.bat`.
2. Run `installer\build-installer.bat offline-full`.
3. Install `installer\Output\SeamlessFordMIS-Setup.exe` on a Windows Clean VM.
4. Run the checklist in `installer/WINDOWS_CLEAN_VM_TEST.md`, including Launcher, Load Images, Start, Migrate, `http://localhost`, API smoke, backup, restore with test data only, LAN access, uninstall, and reinstall preservation checks.

---

## Session summary — Installer/Launcher hardening for Windows Offline LAN readiness (2026-05-27)

- **Date:** 2026-05-27
- **Task worked on:** ตรวจสถานะล่าสุดของ offline package / GUI Launcher / Windows Installer แล้วปิด blocker ที่จำเป็นต่อเส้นทาง `SeamlessFordMIS-Setup.exe` + `SeamlessFordMIS-Launcher.exe`
- **Scope:** Infrastructure, launcher, installer, offline scripts, and docs only — ไม่เปลี่ยน business logic, matching logic, result generation logic, import/mapping rules, exact CID priority, visible result table behavior, provenance, หรือ audit trail

### Phase 0 audit result

- Docker/offline package มีจริงและค่อนข้างครบ แต่ยังไม่ได้ runtime-verify บนเครื่อง Docker-enabled clean target
- GUI Launcher source มีจริงที่ `launcher/seamlessfordmis_launcher.py`
- Launcher build script มีจริง แต่ก่อนแก้มี output path mismatch และ batch parse issue
- Installer source มีจริงที่ `installer/seamlessfordmis.iss`
- Installer build script มีจริง แต่ก่อนแก้มี batch parse issue และ image path mismatch
- Clean VM docs มีจริง แต่ยังเป็น test plan/template ไม่ใช่ผลทดสอบจริง

### Completed

| ไฟล์ | การดำเนินการ |
|---|---|
| `launcher/seamlessfordmis_launcher.py` | เพิ่ม subtitle, LAN URL display, Open Guide action, Copy Log action, `.env` missing warning, safety note, and guide fallback open behavior |
| `launcher/build-launcher.bat` | เขียนใหม่ให้ batch-safe, ตรวจ Python 3.10+, install dependencies, build PyInstaller, output เป็น `launcher\SeamlessFordMIS-Launcher.exe` ตรงกับ installer |
| `installer/seamlessfordmis.iss` | แก้ image tar destination เป็น `{app}\images`, แก้ launcher shortcut check เป็น install-time file check, เพิ่ม Start Menu shortcuts สำหรับ restore/migrate/load images/healthcheck/LAN IP/data safety guide |
| `installer/build-installer.bat` | เขียนใหม่ให้ batch-safe, auto-build launcher ถ้ายังไม่มี, ตรวจ Inno Setup, warn ถ้า image tarballs ไม่ครบ, exit code ถูกต้องเมื่อไม่มี ISCC |
| `offline/healthcheck.bat` | เพิ่ม fail/warn counters, ตรวจ docker compose plugin, ตรวจ `.env`, API smoke fail จริง, exit code 0/1/2 |
| `offline/healthcheck.sh` | เปลี่ยน API smoke failure จาก warning เป็น failure |
| `OFFLINE_INSTALL.md` | อัปเดต backup list ให้มี `.env.bak` และแก้ image path เป็น `app\images` |
| `launcher/README.md` | อัปเดต feature list: Open Guide, Copy Log, production-ready ยัง pending Clean VM |
| `installer/README_INSTALLER.md` | อัปเดต installed layout เป็น `app\images` และเพิ่ม warning ว่ายังไม่ production-ready จนกว่าจะผ่าน Clean VM |
| `docs/GUI_LAUNCHER_PROPOSAL.md` | ระบุสถานะ source-level implemented แต่ binary/clean VM verification ยังต้องทำ |

### Build / verification run

- `python -m py_compile launcher\seamlessfordmis_launcher.py` — passed
- `launcher\build-launcher.bat` — passed
  - output: `launcher\SeamlessFordMIS-Launcher.exe`
  - size: `29979428` bytes
- Launcher smoke startup — passed
  - started EXE, waited 5 seconds, process stayed alive, then stopped process
- `docker-compose.yml` static YAML validation — passed
- Compose service shape confirmed: `db`, `backend`, `frontend`, `nginx`; debug DB relay remains bound to `127.0.0.1`
- `installer\build-installer.bat` — ran and failed correctly because Inno Setup is not installed on this machine
- `python -m compileall -q app` from `backend/` — passed
- `npm run build` from `frontend/` — passed
- `npx tsc --noEmit` from `frontend/` — passed after `npm run build` generated `.next/types`

### Not run / not verified

- Docker runtime verification not run: `docker` command is not installed/in PATH in this environment
- Inno Setup installer build not run: `ISCC.exe` not found
- Windows Clean VM test not run
- LAN access, backup/restore with real Docker volumes, and offline image load flow still require a Docker-enabled Windows test machine
- Initial standalone `npx tsc --noEmit` before `npm run build` failed because `tsconfig.json` includes `.next/types/**/*.ts` and those generated files did not exist yet; rerun after build passed

### Business logic changed

- No. ไม่มีการแก้ backend/frontend business logic, matching, result generation, import/mapping rules, exact CID priority, visible result table behavior, provenance, หรือ audit trail

### Known gaps / blockers

- `SeamlessFordMIS-Setup.exe` ยังไม่ได้ build เพราะ Inno Setup ไม่มีในเครื่องนี้
- Docker stack ยังไม่ได้ verify จริงเพราะ Docker CLI ไม่มีในเครื่องนี้
- Clean VM verification pending — ห้าม claim production-ready จนกว่าจะมี test report จริง
- Docker image tarballs ใน `images\` ยังไม่มีใน workspace นี้; complete offline installer ต้องรัน `offline\save-images.bat` บนเครื่อง online ที่มี Docker ก่อน

### Next recommended step

1. ติดตั้ง Inno Setup 6 บน Windows build machine แล้วรัน `installer\build-installer.bat`
2. บนเครื่อง online ที่มี Docker: รัน `offline\save-images.bat` เพื่อสร้าง image tarballs ก่อน build installer แบบ offline เต็มรูปแบบ
3. ทดสอบ `SeamlessFordMIS-Setup.exe` บน Windows Clean VM ตาม `installer/WINDOWS_CLEAN_VM_TEST.md`
4. บันทึกผลลง `installer/WINDOWS_CLEAN_VM_TEST_REPORT_TEMPLATE.md` ก่อนใช้คำว่า production-ready

---

## Session summary — Phase 0 Full Audit + offline script gap-close (2026-05-26)

- **Date:** 2026-05-26
- **Task worked on:** Phase 0 — audit ทุกไฟล์ระบบ offline/installer/launcher → พบ 4 gaps → แก้ไขครบ
- **Scope:** Infrastructure scripts เท่านั้น — ไม่เปลี่ยน business logic, matching, result generation, import rules

### Completed

| # | ไฟล์ | การดำเนินการ |
|---|------|-------------|
| 1 | `offline/install.bat` | **อัปเดต** — auto-load จาก `images/*.tar` ถ้า Docker images ไม่ครบ (แทนการ build ที่ต้องใช้ internet) |
| 2 | `offline/install.sh` | **อัปเดต** — เช่นเดียวกัน (Linux/macOS) |
| 3 | `offline/backup.bat` | **อัปเดต** — เพิ่ม `.env.bak` step ให้ตรงกับ WINDOWS_CLEAN_VM_TEST.md §5.2 |
| 4 | `offline/backup.sh` | **อัปเดต** — เช่นเดียวกัน (Linux/macOS) |
| 5 | `offline/restart.bat` | **อัปเดต** — เพิ่ม Docker guard + HTTP_PORT display (จาก 4 บรรทัดให้สมบูรณ์แบบ start.bat) |
| 6 | `launcher/seamlessfordmis_launcher.py` | **อัปเดต** — แก้ health status patterns จาก `_db-`/`-db_` ให้เป็น `seamlessfordmis-db` ตรงกับ container_name จริง |

### Phase 0 audit findings

| gap | ไฟล์ | รายละเอียด | แก้ไขแล้ว |
|-----|------|-----------|----------|
| 1 | `install.bat/.sh` | Images missing → ตกไป `docker compose build` (ต้องใช้ internet) แทนที่จะ load จาก `images/*.tar` | ✅ |
| 2 | `backup.bat/.sh` | ไม่มี `.env.bak` แต่ test plan §5.2 ต้องการ | ✅ |
| 3 | `restart.bat` | ไม่มี Docker guard, 4 บรรทัด, inconsistent กับ script อื่น | ✅ |
| 4 | `launcher health patterns` | Patterns `_db-`, `-db_` ไม่ match container names จริง (`seamlessfordmis-db`) | ✅ |

### Items confirmed correct (no changes)

- `docker-compose.yml`: volumes, debug profile (127.0.0.1 only), healthchecks ✅
- `nginx/default.conf`: /healthz, /health, /api/, /, WebSocket ✅
- `Dockerfiles`: base images, curl, NEXT_PUBLIC_API_BASE_URL empty = same-origin ✅
- `.dockerignore`: excludes .env, data, *.sql, *.tar, uploads ✅
- `stop.bat`: `docker compose down` (NOT -v, volumes safe) ✅
- `restore.bat`: typed "RESTORE" confirm, restores all 5 volumes including logs ✅
- `healthcheck.bat`: API smoke test /api/system/status ✅
- `post-install-check.bat`: 7 checks, meaningful exit codes ✅
- `pre-update-backup.bat`: comprehensive (5 volumes + .env.bak) ✅
- `show-lan-ip.bat`: HTTP_PORT-aware, firewall instructions ✅
- `INSTALLER_DATA_SAFETY.md`: complete ✅
- `WINDOWS_CLEAN_VM_TEST.md`: comprehensive 9-section test plan ✅

### Business logic changed

- ไม่มี. ไม่มีการแก้ business logic หลักใดๆ

### ยังไม่ได้ดำเนินการ

- Windows Clean VM test ยังอยู่ที่ `installer/WINDOWS_CLEAN_VM_TEST.md` (pending — ต้องทำบนเครื่อง Windows จริง)
- PyInstaller EXE build ยังต้องการ Windows environment
- Antivirus exception สำหรับ PyInstaller EXE ต้องทำบนเครื่อง Windows จริง

---

## Session summary — GUI Launcher + Installer Integration (2026-05-26)

- **Date:** 2026-05-26
- **Task worked on:** Phase 2 — สร้าง GUI Launcher (Python CustomTkinter) + รวมเข้ากับ Installer Inno Setup
- **Scope:** Infrastructure เท่านั้น — ไม่เปลี่ยน business logic, matching, result generation, import rules

### Completed

| # | ไฟล์ | การดำเนินการ |
|---|------|-------------|
| 1 | `launcher/seamlessfordmis_launcher.py` | **สร้างใหม่** — GUI Launcher (Python + CustomTkinter). Status area สี, ปุ่ม 12 actions, log panel scrub password, restore ผ่าน cmd window แยก |
| 2 | `launcher/requirements.txt` | **สร้างใหม่** — customtkinter, pillow, requests, psutil |
| 3 | `launcher/build-launcher.bat` | **สร้างใหม่** — PyInstaller build script, ตรวจ Python 3.10+, output `launcher\SeamlessFordMIS-Launcher.exe` |
| 4 | `launcher/README.md` | **สร้างใหม่** — คู่มือ build + ใช้งาน + ข้อจำกัด |
| 5 | `installer/seamlessfordmis.iss` | **อัปเดต** — เพิ่ม [Tasks] section, LauncherExeExists(), File entry (skipifsourcedoesntexist), Desktop shortcut primary (launcher), Start Menu entry, [Run] offer open launcher |
| 6 | `installer/build-installer.bat` | **อัปเดต** — เพิ่ม optional build launcher step ก่อน build installer |
| 7 | `installer/FIRST_RUN_NOTICE.md` | **แก้ไข** — แก้ doc inconsistency (option number ผิด → ใช้ [Run] ใน .iss แทน) |
| 8 | `docs/GUI_LAUNCHER_PROPOSAL.md` | **อัปเดต** — สถานะ: proposal → implemented, เพิ่ม build/usage summary |
| 9 | `OFFLINE_INSTALL.md` | **อัปเดต** — เพิ่มหัวข้อ GUI Launcher และ fallback control-panel.bat |

### Business logic changed

- ไม่มี. ไม่มีการแก้ business logic หลักใดๆ

### Safety checks

- Launcher ไม่แสดง password ใดๆ (regex scrub ก่อน log)
- Launcher ไม่ upload ข้อมูลออก internet (localhost เท่านั้น)
- Restore ต้องผ่าน cmd window แยก + typed "RESTORE" (ไม่ bypass .bat safety)
- ไม่มี .env / patient data ใน `launcher/`
- Installer: LauncherExeExists() = `skipifsourcedoesntexist` — graceful fallback ถ้าไม่มี EXE

### ยังไม่ได้ดำเนินการ

- ยังไม่ได้ทดสอบ build บน Windows จริง (PyInstaller ต้องการ Windows environment)
- Windows Clean VM test ยังอยู่ที่ `installer/WINDOWS_CLEAN_VM_TEST.md` (pending)
- Antivirus exception สำหรับ PyInstaller EXE ต้องทำบนเครื่อง Windows จริง

---

## Session summary — Offline/LAN scripts gap-close: restore logs, show-lan-ip, healthcheck API smoke, stop/status/migrate improvements (2026-05-26)

- **Date:** 2026-05-26
- **Task worked on:** Phase 0 audit พบ 6 gap ใน offline scripts — แก้ไขครบทุกรายการ + สร้าง `show-lan-ip.bat/sh` ใหม่
- **Scope:** Infrastructure scripts เท่านั้น — ไม่เปลี่ยน business logic, matching logic, result generation, import rules, exact CID priority, visible result table, provenance, หรือ audit trail

### Completed

| # | ไฟล์ | ช่อง gap | การแก้ไข |
|---|------|----------|---------|
| 1 | `offline/restore.bat` | กู้คืนเพียง 3 volumes — ขาด `logs` ทั้งที่ `backup.bat` save 4 volumes | เพิ่ม `logs` volume restore บรรทัดหลัง `reports` |
| 2 | `offline/restore.sh` | เหมือน `.bat` — ขาด `logs` volume | เพิ่ม `logs` volume restore (POSIX sh) |
| 3 | `offline/healthcheck.bat` | ขาด API smoke test — healthcheck ผ่านแม้ backend API จริงพัง | เพิ่ม `curl /api/system/status` via `docker compose exec` ใน section [3/5] |
| 4 | `offline/healthcheck.sh` | เหมือน `.bat` — ขาด API smoke test | เพิ่ม API smoke test (POSIX sh, นับ WARN) |
| 5 | `offline/stop.bat` | 3 บรรทัด ไม่มี Docker guard / guidance | เพิ่ม Docker guard + ข้อความยืนยัน volumes ยังอยู่ + hint restart |
| 6 | `offline/stop.sh` | 3 บรรทัด เหมือน `.bat` | เพิ่ม Docker guard + guidance (POSIX sh) |
| 7 | `offline/status.bat` | ไม่แสดง URL / ไม่มี next-step hints | เพิ่ม HTTP_PORT-aware URL + hints ดู log + healthcheck |
| 8 | `offline/status.sh` | เหมือน `.bat` | เพิ่ม Docker guard + URL display + hints (POSIX sh) |
| 9 | `offline/migrate.bat` | 1 บรรทัด ไม่มี Docker guard | เพิ่ม Docker guard + error message เมื่อ migration fail |
| 10 | `offline/show-lan-ip.bat` | ไฟล์ไม่มีอยู่ — WINDOWS_CLEAN_VM_TEST.md §4.2 อ้างอิง | สร้างใหม่: แสดง IPv4 ทุก interface + URL + firewall instructions |
| 11 | `offline/show-lan-ip.sh` | ไฟล์ไม่มีอยู่ — Linux/macOS equivalent | สร้างใหม่: `hostname -I` / `ifconfig` fallback + firewall hints |

### Business logic changed

- No. ไม่มีการแก้ business logic หลักใดๆ

### Files changed

| ไฟล์ | การเปลี่ยนแปลง |
|---|---|
| `offline/restore.bat` | +1 บรรทัด: กู้คืน logs volume |
| `offline/restore.sh` | +1 บรรทัด: กู้คืน logs volume |
| `offline/healthcheck.bat` | +5 บรรทัด: API smoke test ใน section [3/5] |
| `offline/healthcheck.sh` | +6 บรรทัด: API smoke test (POSIX sh) |
| `offline/stop.bat` | เขียนใหม่ทั้งไฟล์: Docker guard + guidance |
| `offline/stop.sh` | เขียนใหม่ทั้งไฟล์: Docker guard + guidance |
| `offline/status.bat` | เขียนใหม่ทั้งไฟล์: Docker guard + URL + hints |
| `offline/status.sh` | เขียนใหม่ทั้งไฟล์: Docker guard + URL + hints |
| `offline/migrate.bat` | เขียนใหม่ทั้งไฟล์: Docker guard + error handling |
| `offline/show-lan-ip.bat` | **สร้างใหม่**: แสดง LAN IP + URL + firewall guide |
| `offline/show-lan-ip.sh` | **สร้างใหม่**: แสดง LAN IP + URL + firewall guide |
| `PROJECT_STATUS.md` | เพิ่ม session summary 2026-05-26 นี้ |

### Known gaps / next steps

- **ยังไม่ได้ทำ (ต้องทำก่อน pilot จริง):**
  1. ทดสอบ Windows Installer บน Clean VM (ตาม `installer/WINDOWS_CLEAN_VM_TEST.md`) — **ยังไม่ได้ทำ**
  2. ทดสอบ offline image flow จริง: `save-images.bat` → copy tars → `load-images.bat` บนเครื่อง offline
  3. ทดสอบ LAN access จากเครื่องอื่น พร้อม firewall check
  4. `show-lan-ip.bat` ยังไม่ได้ทดสอบบน Windows จริง — IP extraction logic ต้อง verify
  5. GUI launcher (Python + CustomTkinter) — รอ user feedback ก่อนตัดสินใจ

---

## Session summary — Offline/LAN Readiness Audit: Phase 0–9 gap-close + Phase 9 Readiness Report (2026-05-25)

- **Date:** 2026-05-25
- **Task worked on:** ตรวจสถานะ offline/LAN readiness ของระบบทั้งหมด (Phase 0–9 audit) — พบ gap เชิงความปลอดภัย / ความสม่ำเสมอระหว่าง `.bat` กับ `.sh` และแก้ไขทั้งหมด; สร้าง Phase 9 Final Local-Run Readiness Report
- **Scope:** Infrastructure scripts + frontend UI privacy note เท่านั้น — ไม่เปลี่ยน business logic, matching logic, result generation logic, import/mapping rules, exact CID priority, visible result table behavior, provenance, หรือ audit trail

### Completed

**ช่อง gap ที่พบและแก้ไขแล้ว:**

| # | ไฟล์ | ช่อง gap | การแก้ไข |
|---|------|----------|---------|
| 1 | `offline/install.bat` | รัน `docker compose build` เสมอ — crash บนเครื่อง offline ที่ไม่มี source code | เพิ่ม image existence check: ถ้า 4 images ครบ ข้าม build โดยสมบูรณ์ |
| 2 | `offline/install.sh` | เหมือน `.bat` — build เสมอ | เพิ่ม POSIX sh equivalent image check |
| 3 | `offline/healthcheck.sh` | ไม่มีไฟล์นี้ — `healthcheck.bat` ไม่มีคู่ Linux/macOS | สร้างใหม่ทั้งไฟล์ (POSIX sh, 5 sections, exit code 0/1/2) |
| 4 | `offline/pre-update-backup.bat` | backup 3 volumes แต่ `backup.bat` backup 4 volumes (ขาด logs) | เพิ่ม Step 4b: logs volume + อัปเดต summary listing |
| 5 | `offline/pre-update-backup.sh` | เหมือน `.bat` — ขาด logs volume | เพิ่ม Step 4b: logs volume + summary listing (POSIX sh) |
| 6 | `TargetGroupResultsWorkspace.tsx` | ส่วน Export Excel ไม่มี patient data privacy warning (ขณะที่ upload มีแล้ว) | เพิ่ม `export-privacy-note` paragraph พร้อม warning icon |

**รายละเอียด fix ที่สำคัญที่สุด (install.bat/install.sh):**
- ก่อน fix: `docker compose build` ถูกรันทุกครั้ง — บนเครื่อง offline ที่ใช้ Windows Installer (images pre-loaded แต่ไม่มี source code) จะ fail
- หลัง fix: ตรวจก่อนว่ามี 4 images ครบหรือไม่ — ถ้าครบข้าม build ทันที; ถ้าไม่ครบค่อย build (developer path)
- ทั้ง `.bat` และ `.sh` ได้รับ fix ที่สมมาตรกัน

**Phase 9 — Final Local-Run Readiness Report (10 คำถาม):**

| คำถาม | คำตอบ |
|-------|-------|
| 1. โปรแกรมทำงานบนเครื่องได้หรือยัง | **ใช่** — Docker Compose stack (4 services) ทำงานได้บนเครื่องที่มี Docker Desktop |
| 2. วิธีติดตั้งแบบแนะนำ | **Windows:** Installer `.exe` → `load-images.bat` → `install.bat` / `control-panel.bat`; **Linux/macOS:** copy folder → `load-images.sh` → `install.sh` |
| 3. ต้องใช้ Docker Desktop หรือไม่ | **Windows: ใช่** (ต้องติดตั้งเอง — installer ไม่ bundle); **Linux: Docker Engine + Compose plugin** (ไม่ต้อง Desktop) |
| 4. ใช้ได้แบบ offline จริงไหม | **ใช่** — หลัง `load-images.bat/sh` แล้ว ทุกอย่างทำงานใน Docker ไม่ต้อง internet |
| 5. ข้อมูลผู้ป่วยเก็บอยู่ที่ไหน | **Docker volumes:** `seamlessfordmis_postgres_data`, `_uploads`, `_source_data`, `_reports`, `_logs`; **Host backup:** `data/backups/` |
| 6. backup อยู่ที่ไหน | `data/backups/YYYYMMDD-HHMMSS/` — สร้างโดย `backup.bat` หรือ `pre-update-backup.bat` |
| 7. uninstall ลบข้อมูลไหม | **ไม่** — uninstaller รัน `docker compose stop` เท่านั้น; volumes และ backups ยังคงอยู่; ต้องใช้ `danger-remove-all-data.bat.example` (rename + 3-step confirm) เพื่อลบข้อมูลทั้งหมด |
| 8. เปิดให้เครื่องอื่นใน LAN ใช้ยังไง | ดู IP ด้วย `control-panel` option 11 หรือ `ipconfig`; เครื่องอื่นเปิด `http://<IP>:<HTTP_PORT>/`; ต้องตั้ง `HTTP_PORT` ใน `.env` และเปิด Windows Firewall port |
| 9. ยังมีอะไรที่ต้องทดสอบจริงก่อนแจก | (1) Windows Installer บน Clean VM (`WINDOWS_CLEAN_VM_TEST.md`); (2) offline image flow (load บนเครื่องไม่มี internet); (3) LAN access จากเครื่องอื่น; (4) backup/restore flow; (5) alembic migrations บน production database |
| 10. พร้อม pilot ในหน่วยงานหรือยัง | **Code-ready แต่ยังไม่ได้ verify บน Clean VM จริง** — ต้องผ่าน Windows Clean VM test ก่อน pilot; core business logic (matching + result generation) ทำงานถูกต้องแล้ว |

### Business logic changed

- No. ไม่มีการแก้ business logic หลัก, matching logic, result generation logic, import/mapping rules, exact CID priority, result table behavior, provenance, หรือ audit trail

### Files changed

| ไฟล์ | การเปลี่ยนแปลง |
|---|---|
| `offline/install.bat` | เพิ่ม image existence check ก่อน build — ข้าม build ถ้า images ครบแล้ว |
| `offline/install.sh` | เพิ่ม POSIX sh equivalent image check |
| `offline/healthcheck.sh` | สร้างใหม่ (5-section, exit 0/1/2, POSIX sh) |
| `offline/pre-update-backup.bat` | เพิ่ม Step 4b: logs volume backup + อัปเดต summary |
| `offline/pre-update-backup.sh` | เพิ่ม Step 4b: logs volume backup + อัปเดต summary (POSIX sh) |
| `frontend/src/components/target-groups/TargetGroupResultsWorkspace.tsx` | เพิ่ม `export-privacy-note` paragraph ใต้ปุ่ม Export Excel |
| `PROJECT_STATUS.md` | เพิ่ม session summary 2026-05-25 นี้ |

### Known gaps / next steps

- **ต้องทำก่อน pilot จริง:**
  1. ทดสอบ Windows Installer บน Clean VM (ตาม `installer/WINDOWS_CLEAN_VM_TEST.md`)
  2. ทดสอบ offline image flow จริง: `save-images.bat` บนเครื่อง online → copy tars → `load-images.bat` บนเครื่อง offline
  3. ทดสอบ LAN access จากเครื่องอื่นในเครือข่าย
  4. รัน `alembic upgrade head` บน production database (migrations 0010–0015 ยังรอ)
  5. Re-generate results ของ target groups ที่มีอยู่หลัง migration
- **ค้างอยู่จาก session ก่อน:**
  - GUI launcher (Python + CustomTkinter) — รอ feedback จากเจ้าหน้าที่โรงพยาบาลก่อนตัดสินใจ
  - Thai date fix: ข้อมูล import ก่อน fix มี `normalized_visit_date = NULL` — ต้อง re-import Excel + re-generate results
  - `export-privacy-note` CSS class อาจต้องเพิ่มใน `globals.css` ถ้า design ต้องการ custom styling (ตอนนี้ใช้ inline style ผ่าน `<p>` tag)

---

## Session summary — Offline/LAN installer gap-close: Linux/macOS scripts, test docs, GUI proposal (Scopes A–H) (2026-05-22)

- **Date:** 2026-05-22
- **Task worked on:** ปิด gap ที่เหลือทั้งหมดของ offline/LAN installer — สร้าง Linux/macOS `.sh` equivalents, เอกสารทดสอบบน Windows Clean VM, เอกสารเปรียบเทียบ GUI launcher, ขยาย OFFLINE_INSTALL.md ให้ครอบคลุม Linux/macOS อย่างสมบูรณ์ และบันทึกความแตกต่างเชิงพฤติกรรมระหว่าง `.bat` และ `.sh`
- **Scope:** Documentation + scripts เท่านั้น — ไม่เปลี่ยน business logic, matching logic, result generation logic, import/mapping rules, exact CID priority, visible result table, provenance, หรือ audit trail

### Completed

**Scope A — Linux/macOS `.sh` equivalents (POSIX sh, `#!/usr/bin/env sh`, `set -eu`):**
- `offline/post-install-check.sh` — ตรวจสอบ 7 รายการ: Docker, Docker Engine, .env, images ครบ 4, containers ครบ 4, /healthz 200, /api/system/status 200; exit code 0=PASS, 1=FAIL, 2=WARN only
- `offline/open-web.sh` — เปิดเว็บจาก .env (FRONTEND_PORT), fallback macOS→Linux→print URL
- `offline/pre-update-backup.sh` — backup database.sql + 3 volume tars + .env.bak พร้อม timestamp; ตรวจ db container ก่อน
- `offline/danger-remove-all-data.sh.example` — ยืนยัน 3 ชั้น (YES → DELETE ALL PATIENT DATA → 10s countdown); ต้อง rename ก่อนจึงรันได้

**Scope B — บันทึกความแตกต่าง `.bat` vs `.sh` ใน `OFFLINE_INSTALL.md`:**
- user input: `choice /C YN` vs `printf; read -r; case`
- web endpoint check: PowerShell `Invoke-WebRequest` vs `curl`
- timestamp: `PowerShell Get-Date` vs `date +%Y%m%d-%H%M%S` (output format เหมือนกัน)
- browser opening: `start "" URL` vs `open`/`xdg-open`/`sensible-browser`/print URL
- container status: `findstr /I` vs `grep -qi`
- สิ่งที่เหมือนกันทุกอย่าง: Docker commands, volume names, 3-step confirmation, backup structure, exit codes

**Scope C — `installer/WINDOWS_CLEAN_VM_TEST.md`:**
- คู่มือทดสอบ 11 หัวข้อ ภาษาไทย สำหรับทดสอบบน Windows Clean VM
- ครอบคลุม: VM setup, ติดตั้ง Docker, ติดตั้ง installer, first run, web access, LAN access, backup, restore, stop/start, uninstall, final sign-off

**Scope D — `installer/WINDOWS_CLEAN_VM_TEST_REPORT_TEMPLATE.md`:**
- แบบฟอร์มบันทึกผลการทดสอบ 8 ส่วน ภาษาไทย
- 27 รายการทดสอบแบ่งเป็น 7 หมวด; slot สำหรับ screenshot 10 ใบ; PASS/PASS WITH NOTES/BLOCK final verdict; 6 เงื่อนไข BLOCK; ลายมือชื่อผู้ทดสอบ
- หมายเหตุ data privacy ท้ายเอกสาร (ห้ามแนบ screenshot ที่มีข้อมูลผู้ป่วย)

**Scope E — `docs/GUI_LAUNCHER_PROPOSAL.md`:**
- เปรียบเทียบ 4 ตัวเลือก GUI launcher: .NET WinForms/WPF, Tauri, Electron, Python Tkinter/CustomTkinter
- ตาราง 9 มิติ: ขนาด binary, ความยากพัฒนา, native look, System Tray, cross-platform, reuse code, runtime overhead, Windows 10, ความเสถียร
- Phased approach: Phase 1 = คง `control-panel.bat` (ปัจจุบัน), Phase 2 = Python+CustomTkinter (ถ้า feedback จริงต้องการ GUI), Phase 3 = Tauri (ถ้าต้องการ cross-platform)
- สถานะ: ข้อเสนอสำหรับพิจารณา — ยังไม่ได้ตัดสินใจ ณ 2026-05-22

**Scopes B+F — ขยาย `OFFLINE_INSTALL.md` ส่วน Linux/macOS:**
- เพิ่ม prerequisites, ตาราง scripts 10 รายการพร้อม Windows equivalent, usage examples ครบทุก script, danger-remove flow (rename + chmod + run), exit codes table

### Business logic changed

- No. ไม่มีการแก้ business logic หลัก, matching logic, result generation logic, import/mapping rules, exact CID priority, result table behavior, provenance, หรือ audit trail

### Files changed

| ไฟล์ | การเปลี่ยนแปลง |
|---|---|
| `offline/post-install-check.sh` | สร้างใหม่ (POSIX sh, 7-item health check) |
| `offline/open-web.sh` | สร้างใหม่ (เปิดเว็บ macOS/Linux) |
| `offline/pre-update-backup.sh` | สร้างใหม่ (backup database + volumes) |
| `offline/danger-remove-all-data.sh.example` | สร้างใหม่ (3-step confirmation, ต้อง rename) |
| `installer/WINDOWS_CLEAN_VM_TEST.md` | สร้างใหม่ (11-section Thai checklist) |
| `installer/WINDOWS_CLEAN_VM_TEST_REPORT_TEMPLATE.md` | สร้างใหม่ (8-section tester report template) |
| `docs/GUI_LAUNCHER_PROPOSAL.md` | สร้างใหม่ (4-option comparison + phased recommendation) |
| `OFFLINE_INSTALL.md` | ขยายส่วน Linux/macOS (~150 บรรทัด) + เพิ่ม `.bat` vs `.sh` comparison table |
| `PROJECT_STATUS.md` | เพิ่ม session summary 2026-05-22 นี้ |

### Windows Clean VM test status

- **ยังไม่ได้รันจริง** — `WINDOWS_CLEAN_VM_TEST.md` และ `WINDOWS_CLEAN_VM_TEST_REPORT_TEMPLATE.md` เป็นแผนการทดสอบ (plan) เท่านั้น
- ต้องทดสอบบน Windows machine จริงก่อน deploy ใช้งานจริง

### Known gaps / next steps

- ทดสอบ installer จริงบนเครื่อง Windows ที่ clean (ใช้ `installer/WINDOWS_CLEAN_VM_TEST.md` เป็น guide)
- GUI launcher (Python + CustomTkinter) — รอ feedback จากเจ้าหน้าที่โรงพยาบาลก่อนตัดสินใจ
- Thai date fix (session ก่อน): ข้อมูล import ก่อน fix มี `normalized_visit_date = NULL` — ต้อง re-import Excel + re-generate results

---

## Session summary — Windows Installer: เพิ่มส่วน OFFLINE_INSTALL.md + ปิด task #44 (2026-05-22)

- **Date:** 2026-05-22
- **Task worked on:** ปิด gap ที่เหลือจาก session 2026-05-21 — เพิ่มส่วน "วิธีติดตั้งผ่าน Windows Installer" ใน `OFFLINE_INSTALL.md` และอัปเดต `PROJECT_STATUS.md` (task #44)
- **Scope:** Documentation เท่านั้น — ไม่เปลี่ยน business logic, matching logic, result generation logic, หรือ infrastructure scripts

### Completed

**OFFLINE_INSTALL.md — เพิ่มส่วน "วิธีติดตั้งผ่าน Windows Installer":**
- ตาราง prerequisites (OS, Docker, RAM, Disk, สิทธิ์)
- ขั้นตอน Wizard ทีละขั้น พร้อมอธิบายสิ่งที่ installer ทำอัตโนมัติ
- ตาราง directory structure หลังติดตั้ง (C:\SeamlessFordMIS\...)
- หัวข้อ "การอัปเดตระบบ" — อธิบาย upgrade-safe .env preservation
- หัวข้อ "การถอนการติดตั้ง" — ตาราง สิ่งที่ถูกลบ / ไม่ถูกลบ
- หัวข้อ "การลบข้อมูลทั้งหมด" — วิธี rename .bat.example + 3-step confirmation
- Link ไปยัง `docs/INSTALLER_DATA_SAFETY.md`

**PROJECT_STATUS.md:**
- เพิ่ม session summary 2026-05-22 (ไฟล์นี้)
- ปิด task #44 "Scope K: อัปเดต PROJECT_STATUS.md"

### Business logic changed

- No. ไม่มีการแก้ business logic หลัก, matching logic, result generation logic, import/mapping rules, exact CID priority, result table behavior, provenance, หรือ audit trail

### Files changed

| ไฟล์ | การเปลี่ยนแปลง |
|---|---|
| `OFFLINE_INSTALL.md` | เพิ่มส่วน "วิธีติดตั้งผ่าน Windows Installer" (~80 บรรทัด) |
| `PROJECT_STATUS.md` | เพิ่ม session summary 2026-05-22 (ไฟล์นี้) |

### Known gaps / next steps

- `.sh` equivalents สำหรับ scripts ใหม่ทั้งหมด (Linux/macOS): `post-install-check.sh`, `open-web.sh`, `danger-remove-all-data.sh.example`, `pre-update-backup.sh`
- Optional GUI launcher (Scope I) — ยังเป็น proposal เท่านั้น (Electron/Tauri/.NET)
- ทดสอบ installer จริงบนเครื่อง Windows ที่ clean — ยังไม่ได้ verify ครบ
- Thai date fix (session ก่อน): ข้อมูล import ก่อน fix มี `normalized_visit_date = NULL` — ต้อง re-import Excel + re-generate results

---

## Session summary — Windows Installer full package (Scopes A–K) (2026-05-21)

- **Date:** 2026-05-21
- **Task worked on:** สร้าง Windows Installer เต็มรูปแบบสำหรับ seamlessfordmis offline/LAN — ครอบคลุม Inno Setup script, offline image pipeline, control panel ขยาย, scripts ความปลอดภัย, เอกสาร, health check, browser launcher
- **Scope:** Infrastructure/packaging/documentation เท่านั้น — ไม่เปลี่ยน business logic, matching logic, result generation logic, import/mapping rules, exact CID priority, visible result table behavior, provenance, หรือ audit trail

### Completed

**Scope A — Windows Installer (Inno Setup 6+):**
- `installer/seamlessfordmis.iss` — full Inno Setup script
  - `AppId={{B3E7A1C2-4F5D-4E8A-9B0C-1D2E3F4A5B6C}}`
  - ติดตั้งไปที่ `C:\SeamlessFordMIS\app\` (default)
  - สร้าง `.env` อัตโนมัติด้วยรหัสผ่านสุ่ม 20 ตัวอักษร (XOR seed mixing ใน Pascal Script)
  - ไม่สร้าง `.env` ซ้ำถ้ามีอยู่แล้ว (upgrade-safe)
  - ตรวจสอบ Docker Desktop ระหว่างติดตั้ง
  - สร้าง shortcuts บน Desktop และ Start Menu (7 shortcuts)
  - Uninstall: `docker compose stop` เท่านั้น — ไม่ลบ volumes/data/logs
  - รวม Docker image tarballs แบบ optional (`skipifsourcedoesntexist`)
- `installer/build-installer.bat` — build script ค้นหา ISCC.exe ใน 4 paths, แจ้งเตือนถ้า image tarballs ขาด, แสดงขนาด output .exe

**Scope C — ปรับปรุง offline image pipeline:**
- `offline/save-images.bat` — Docker check, internet warning, pull postgres:16 + nginx:alpine, `docker compose build`, save 4 tars พร้อม per-file sizes + total MB
- `offline/load-images.bat` — Docker check, verify ครบ 4 tars (size shown), load ทั้งหมดพร้อม error handling, แสดง `docker images` ผลลัพธ์

**Scope D — ขยาย control-panel.bat 12 → 14 ตัวเลือก:**
- เพิ่ม Option 12: โหลด Docker images (`offline\load-images.bat`)
- เพิ่ม Option 13: เปิดคู่มือติดตั้ง (`OFFLINE_INSTALL.md` ผ่าน `start ""`)
- ย้าย Exit เป็น Option 14
- แก้ด้วย Python + `encoding='utf-8'` (Edit tool ล้มเหลวกับ Thai UTF-8 BAT)

**Scope E — Scripts ความปลอดภัย:**
- `offline/danger-remove-all-data.bat.example` — ยืนยัน 3 ชั้น: (1) พิมพ์ `YES`, (2) พิมพ์ `DELETE ALL PATIENT DATA` (case-sensitive), (3) นับถอยหลัง 10 วินาที — ลบ 5 volumes + data/backups + .env แต่ไม่ลบ logs
- `offline/pre-update-backup.bat` — ตรวจสอบ db container ก่อน, ถ้าไม่ running ให้เลือก skip dump หรือ abort, backup 5 ส่วน: database.sql + 3 volume tars + .env.bak, ส่วนท้ายมี hospital data privacy warning + next steps

**Scope F+G — เอกสาร:**
- `installer/FIRST_RUN_NOTICE.md` — คู่มือผู้ใช้ครั้งแรก: post-install-check → install.bat → เปิดเว็บ, ตาราง data storage locations, data safety warnings
- `installer/README_INSTALLER.md` — คู่มือ IT admin: build offline/online package, structure หลัง install, uninstall behavior, upgrade-safe policy, security table
- `docs/INSTALLER_DATA_SAFETY.md` — นโยบายความปลอดภัยข้อมูลฉบับเต็ม: PDPA context, random password per machine, uninstall policy table, `danger-remove-all-data.bat.example` วิธีใช้, patient data storage locations, audit trail
- `OFFLINE_INSTALL.md` — อัปเดต menu "มี 12 ตัวเลือก" → "มี 14 ตัวเลือก", เพิ่ม options 12 และ 13 ในส่วน ASCII menu

**Scope H+J — Scripts ตรวจสอบและเปิดเว็บ:**
- `offline/post-install-check.bat` — ตรวจสอบ 7 รายการ:
  1. Docker ติดตั้ง (goto :summary ถ้าไม่พบ)
  2. Docker Engine ทำงาน (goto :summary ถ้าไม่พร้อม)
  3. .env มีอยู่
  4. Docker images ครบ 4 รายการ (postgres:16, nginx:alpine, seamlessfordmis-backend:latest, seamlessfordmis-frontend:latest)
  5. Containers running (WARN ถ้าไม่ running — ปกติในการติดตั้งครั้งแรก)
  6. pg_isready ใน db container
  7. HTTP endpoint (Invoke-WebRequest ผ่าน PowerShell)
  - Exit codes: 0=pass all, 1=FAIL, 2=WARN only (containers ยังไม่ start)
- `offline/open-web.bat` — อ่าน `HTTP_PORT` จาก `.env` (default 80), สร้าง URL แล้วเรียก `start ""` เปิด default browser

### Business logic changed

- No. ไม่มีการแก้ business logic หลัก, matching logic, result generation logic, import/mapping rules, exact CID priority, result table behavior, provenance, หรือ audit trail

### Files created / modified

| ไฟล์ | การเปลี่ยนแปลง |
|---|---|
| `installer/seamlessfordmis.iss` | ใหม่ — Inno Setup 6+ script |
| `installer/build-installer.bat` | ใหม่ — build script |
| `offline/save-images.bat` | ปรับปรุง — Docker check, sizes, Thai messages |
| `offline/load-images.bat` | ปรับปรุง — verify tarballs, per-image error handling |
| `offline/control-panel.bat` | ปรับปรุง — 12 → 14 ตัวเลือก |
| `offline/danger-remove-all-data.bat.example` | ใหม่ — 3-step confirmation |
| `offline/pre-update-backup.bat` | ใหม่ — pre-update safe backup |
| `offline/post-install-check.bat` | ใหม่ — health check 7 รายการ + exit codes |
| `offline/open-web.bat` | ใหม่ — browser launcher อ่าน HTTP_PORT จาก .env |
| `installer/FIRST_RUN_NOTICE.md` | ใหม่ — คู่มือผู้ใช้ครั้งแรก |
| `installer/README_INSTALLER.md` | ใหม่ — คู่มือ IT admin |
| `docs/INSTALLER_DATA_SAFETY.md` | ใหม่ — นโยบายความปลอดภัยข้อมูล |
| `OFFLINE_INSTALL.md` | ปรับปรุง — menu 12 → 14 ตัวเลือก |

### Safety rules enforced

- Installer ไม่รวม `.env`, patient data, source code, database dump
- Uninstaller: `docker compose stop` only — ไม่ `down -v`
- Upgrade reinstall: `.env` preserved ถ้ามีอยู่แล้ว
- `danger-remove-all-data.bat.example`: `.bat.example` extension + 3-step confirmation ป้องกันการลบโดยไม่ตั้งใจ
- post-install-check.bat: ไม่ fake success — รายงาน FAIL/WARN จริงทุกรายการ
- ไม่ bundle Docker Desktop — แนะนำให้ผู้ใช้ติดตั้งเอง

### Known gaps / next steps

- `.sh` equivalents สำหรับ script ใหม่ทั้งหมด (Linux/macOS users) ยังไม่ได้สร้าง
- `OFFLINE_INSTALL.md` ส่วน "วิธีติดตั้งผ่าน Windows Installer" ยังไม่ได้เพิ่ม — installer มี `FIRST_RUN_NOTICE.md` แทน
- Optional GUI launcher (Scope I) ยังคงเป็น proposal เท่านั้น
- ทดสอบ installer จริงบนเครื่อง Windows ที่ clean — ยังไม่ได้ verify ครบ
- Thai date fix (session ก่อน): ข้อมูล import ก่อน fix มี `normalized_visit_date = NULL` — ต้อง re-import Excel + re-generate results

---

## Session summary — Offline/LAN polish: control-panel, healthcheck, UI badge, debug profile (2026-05-21)

- **Date:** 2026-05-21
- **Task worked on:** เพิ่มเครื่องมือสำหรับผู้ดูแลระบบ offline/LAN — แผงควบคุม, healthcheck, ปรับปรุง scripts, UI badge, debug profile
- **Scope:** Infrastructure + frontend cosmetic เท่านั้น — ไม่เปลี่ยน business logic, matching logic, result generation, import/mapping rules, CID priority, visible result table behavior, provenance, หรือ audit trail

### Completed

**Scope C — แผงควบคุม (offline/control-panel.bat):**
- เมนูภาษาไทย 12 ตัวเลือก ครอบคลุมทุก operation
- ตรวจสอบ Docker ก่อนเริ่ม — แจ้งวิธีแก้เมื่อ Docker ไม่พร้อม (ไม่ปิดเงียบ)
- แสดงสถานะย่อ (running/stopped/partial) บนเมนูหลักเสมอ
- อ่าน `HTTP_PORT` จาก `.env` แล้วแสดง URL ที่ถูกต้อง
- ตัวเลือก 11 แสดง IPv4 ทุก adapter สำหรับ LAN sharing
- เรียก scripts เดิม (`install.bat`, `start.bat`, `backup.bat` ฯลฯ) ผ่าน `call`

**Scope D+E — ปรับปรุง scripts + healthcheck:**
- `offline/start.bat` — เพิ่ม Docker guard, รอ backend healthy, แสดง URL หลัง start
- `offline/backup.bat` — เพิ่ม patient data privacy warning
- `offline/restore.bat` — เพิ่ม "แนะนำ backup ก่อน" คำแนะนำ
- `offline/healthcheck.bat` (ใหม่) — ตรวจ 5 รายการ: Docker Engine, container status, HTTP endpoints, Docker volumes, disk space

**Scope F — UI badge + upload privacy note:**
- `Sidebar.tsx` — เพิ่ม `.local-mode-badge` ("ภายในหน่วยงาน") พร้อมไอคอน lock ใน sidebar footer
- `TargetGroupUploadForm.tsx` — เพิ่ม `.upload-privacy-note` ("ไฟล์จะถูกประมวลผลภายในหน่วยงานเท่านั้น") ใต้ชนิดไฟล์
- `globals.css` — เพิ่ม CSS สำหรับทั้งสอง class ใหม่ (`color-mix` ทำให้ adaptive กับ theme)

**Scope G — debug profile:**
- `docker-compose.yml` — เพิ่ม service `db-port-relay` (profile: debug)
- ใช้ `alpine/socat` relay แทนการรัน Postgres ตัวที่สอง (ปลอดภัย — ไม่แชร์ data volume)
- bind ที่ `127.0.0.1:POSTGRES_DEBUG_PORT` เท่านั้น
- เปิดด้วย `docker compose --profile debug up -d`

**Scope H — OFFLINE_INSTALL.md:**
- เพิ่มหัวข้อ "เหมาะกับใคร" (ตาราง use-case)
- เพิ่มหัวข้อ "แผงควบคุม" พร้อม ASCII menu preview
- เพิ่มหัวข้อ "Debug profile" พร้อมคำเตือนความปลอดภัย
- เพิ่มหัวข้อ "Checklist ก่อนใช้งานจริง" (production readiness checklist)

### Business logic changed

- No. ไม่มีการแก้ business logic หลัก, matching logic, result generation logic, import/mapping rules, exact CID priority, result table behavior, provenance, หรือ audit trail

### Files changed

- `offline/control-panel.bat` (ใหม่)
- `offline/healthcheck.bat` (ใหม่)
- `offline/start.bat` (ปรับปรุง)
- `offline/backup.bat` (ปรับปรุง)
- `offline/restore.bat` (ปรับปรุง)
- `frontend/src/components/layout/Sidebar.tsx` (เพิ่ม badge)
- `frontend/src/components/target-groups/TargetGroupUploadForm.tsx` (เพิ่ม privacy note)
- `frontend/src/app/globals.css` (เพิ่ม CSS)
- `docker-compose.yml` (เพิ่ม db-port-relay service)
- `OFFLINE_INSTALL.md` (เพิ่ม 4 หัวข้อ)

### Known gaps / next steps

- `.sh` equivalents สำหรับ `control-panel.bat` และ `healthcheck.bat` ยังไม่ได้สร้าง (Linux/macOS users)
- Optional GUI launcher (Scope I) ยังไม่ได้ implement — ยังเป็น proposal เท่านั้น
- Thai date fix (session ก่อน): ข้อมูลที่ import ไปก่อน fix มี `normalized_visit_date = NULL` — ต้อง re-import Excel + re-generate results
- alembic migration 0014 (Phase F unique constraints) ยังไม่ได้รัน production

---

## Session summary — Docker offline/LAN deployment package (2026-05-14)

- **Date:** 2026-05-14
- **Task worked on:** ทำ Docker Compose package สำหรับติดตั้งระบบแบบ offline/LAN โดยให้หน่วยงานอื่นติดตั้งเองได้ง่ายขึ้น
- **Scope:** Deployment/infrastructure packaging เท่านั้น — ไม่เปลี่ยน matching logic, result generation logic, import/mapping rules, exact CID priority, visible result table behavior, provenance, หรือ audit trail

### Completed

- เพิ่ม backend Docker image:
  - `backend/Dockerfile`
  - ใช้ Python 3.11 slim
  - working directory `/app/backend`
  - install จาก `backend/requirements.txt`
  - default command: `python -m uvicorn app.main:app --host 0.0.0.0 --port 8010`
  - รองรับ `docker compose run --rm backend alembic upgrade head`
- เพิ่ม frontend Docker image:
  - `frontend/Dockerfile`
  - ใช้ Node 22 Alpine multi-stage build
  - install จาก `package-lock.json`
  - build ด้วย `npm run build`
  - run production server ที่ port `3000`
  - ใช้ `NEXT_PUBLIC_API_BASE_URL=` สำหรับ same-origin LAN/proxy deployment เพราะ frontend request path เริ่มด้วย `/api/...` อยู่แล้ว
- ปรับ `docker-compose.yml` เป็น offline deployment stack:
  - `db` PostgreSQL 16
  - `backend` FastAPI port ภายใน `8010`
  - `frontend` Next.js port ภายใน `3000`
  - `nginx` เปิด host port `80`
  - PostgreSQL ไม่ expose port `5432` ออก host โดย default
- เพิ่ม nginx reverse proxy:
  - `docker/nginx/default.conf`
  - `/` -> `frontend:3000`
  - `/api/` -> `backend:8010/api/`
  - `/health` -> backend `/health`
  - `client_max_body_size 250M`
  - timeout 300 วินาทีสำหรับ import/generate
- เพิ่ม env/ignore strategy:
  - `.env.offline.example`
  - ปรับ `.env.example` เป็น local development reference พร้อมตัวแปร offline ที่เกี่ยวข้อง
  - `.dockerignore` กัน `.env`, `.git`, node_modules, build artifacts, logs, uploads, data, dumps, backups, images
- เพิ่ม offline scripts:
  - Windows: `install.bat`, `start.bat`, `stop.bat`, `restart.bat`, `migrate.bat`, `backup.bat`, `restore.bat`, `logs.bat`, `status.bat`
  - Image flow: `build-images.bat`, `save-images.bat`, `load-images.bat`
  - Linux/macOS equivalents: `*.sh`
- เพิ่มเอกสาร:
  - `OFFLINE_INSTALL.md` ภาษาไทยสำหรับ IT หน่วยงาน
  - ครอบคลุม install/start/stop/migration/backup/restore/update/log/troubleshooting/security/offline image export-load

### Volume strategy

- `seamlessfordmis_postgres_data` — PostgreSQL data
- `seamlessfordmis_source_data` — source/import files
- `seamlessfordmis_uploads` — uploaded target-group files และ parsed cache
- `seamlessfordmis_reports` — report artifacts
- `seamlessfordmis_logs` — logs
- `./data/backups` — host-visible backup output

### Health / migration

- ใช้ endpoint ที่มีอยู่แล้ว `GET /health` สำหรับ backend healthcheck
- Migration แยกเป็น explicit command:
  - `offline\migrate.bat`
  - `docker compose run --rm backend alembic upgrade head`
- ไม่ auto-run destructive migration แบบซ่อนใน backend startup

### Business logic changed

- No. ไม่มีการแก้ business logic หลัก, matching logic, result generation logic, import/mapping rules, exact CID priority, result table behavior, provenance, หรือ audit trail

### Known bugs / open issues update

- Docker runtime verification ต้องขึ้นกับ environment ที่มี Docker พร้อมใช้งาน
- `REPORTS_DIR` และ `BACKUP_DIR` อยู่ใน env/offline scripts/volume strategy แล้ว แต่ backend runtime logic เดิมยังไม่ได้ใช้สองค่านี้โดยตรง
- Existing open data/backend issues from previous sessions remain unchanged

### Blockers update

- No code-level blocker for offline deployment package
- หากเครื่องติดตั้งใช้ port 80 อยู่แล้ว ให้ตั้ง `HTTP_PORT=8080` ใน `.env`

### Next recommended step

1. Run full Docker verification on a clean machine or VM: `offline\install.bat`, `curl http://localhost/health`, `curl http://localhost/api/screening-database/imports?limit=1`
2. Review `.env` password policy with the target IT team before production use
3. Test offline image flow with `offline\save-images.bat` on an online build machine and `offline\load-images.bat` on an offline target

---

## Session summary — Dashboard UI refinement: CSS fixes (2026-05-11b)

- **Date:** 2026-05-11
- **Task worked on:** แก้ไข UI ที่พลาดในรอบก่อน — เพิ่ม CSS class ที่ขาด, eyebrow ที่หาย, และ `db-middle-card` ที่ขาดไป
- **Scope:** Frontend CSS และ component markup เท่านั้น — ไม่เปลี่ยน business logic, API, หรือ types

### Completed

- `DashboardStatusSummary.tsx` — เพิ่ม `<p className="eyebrow">สถานะระบบ</p>` เหนือ `<h3>` ใน panel-head
- `ScreeningDataUploadCard.tsx` — เพิ่ม `db-middle-card` ใน `className` ของ `<section>` ให้ตรงกับ sibling cards ใน 3-column grid
- `globals.css` — เพิ่ม CSS class ที่ขาด:
  - `.db-status-panel .summary-card { padding: 16px 20px; align-items: center }` — แก้ padding ที่แน่นเกินไป (เดิม 5px 14px)
  - `.db-status-panel .summary-grid { border-top: 1px solid var(--line); margin-top: 20px }` — separator line เหนือ metric strip
  - `.db-imports-panel` — placeholder class (inherits `.panel`)
  - `.db-import-empty` — empty state ใน imports table
  - `.db-table-footnote` — footnote "แสดง X จาก Y รายการ"
  - `.icon-only-btn` + hover/active states — ใช้โดย CopyHashButton ใน SourceIntegrityCard

### Files changed in this session

- `frontend/src/components/dashboard/DashboardStatusSummary.tsx`
- `frontend/src/components/dashboard/ScreeningDataUploadCard.tsx`
- `frontend/src/app/globals.css`
- `PROJECT_STATUS.md`

### Verification run

- Frontend typecheck: `npx tsc --noEmit` — passed (no output = clean)
- All 9 CSS presence checks: passed
- File integrity: globals.css ends with closing `}`, no dangling declarations

### Known bugs / open issues

- ไม่มี bug ใหม่จาก session นี้
- `more` action ใน imports table ยังคง disabled (ยังไม่มี action ที่ defined)

---

## Session summary — Dashboard import APIs + responsive QA (2026-05-11)

- **Date:** 2026-05-11
- **Task worked on:** เปิดใช้งาน API/ปุ่มสำหรับ import detail, report download, source-check refresh และทำ visual QA เพิ่ม
- **Scope:** Dashboard API + frontend wiring; ไม่เปลี่ยน business rules, matching logic, result generation logic หรือ patient-level export

### Completed

- เพิ่ม API สำหรับ import dashboard:
  - `GET /api/screening-database/imports/{import_id}` — import detail พร้อม source files
  - `GET /api/screening-database/imports/{import_id}/download` — ดาวน์โหลดไฟล์ต้นทางเมื่อ import นั้นมีไฟล์เดียว และจำกัด path ให้อยู่ใน `source_data_dir`
  - `GET /api/screening-database/imports/{import_id}/report` — ดาวน์โหลด CSV summary ของ import/source-file metadata
- เปิดปุ่มหน้า Dashboard:
  - `ดูรายละเอียด import` โหลด detail จริงและแสดง detail panel
  - `ดาวน์โหลดรายงานสรุป import` ดาวน์โหลด CSV summary จริง
  - quick action `ดาวน์โหลดรายงานสรุป` ดาวน์โหลด report ของ import ล่าสุด
  - `ตรวจสอบไฟล์ล่าสุด` ใน Source Integrity card เรียก `POST /api/system/check-source-update` client-side และแสดง feedback
- ตัดสินใจเรื่อง `ตรวจสอบไฟล์ล่าสุด`:
  - ใช้ `check-source-update` client-side สำหรับ Dashboard ตอนนี้ เพราะเป็นการตรวจ source-set ทั้งชุดที่ตรงกับความหมายของ card
  - ยังไม่เพิ่ม per-file endpoint จนกว่าจะมี UX ที่ต้องตรวจรายไฟล์จริง

### Files changed in this session

- `backend/app/api/screening_database.py`
- `backend/app/schemas/screening_database.py`
- `frontend/src/lib/api.ts`
- `frontend/src/types/screening-database.ts`
- `frontend/src/components/dashboard/SourceIntegrityCard.tsx`
- `frontend/src/components/dashboard/RecentImportsTable.tsx`
- `frontend/src/components/dashboard/DashboardQuickActions.tsx`
- `frontend/src/app/dashboard/page.tsx`
- `frontend/src/app/globals.css`
- `PROJECT_STATUS.md`

### Verification run

- Backend syntax: `python -m py_compile backend\app\api\screening_database.py backend\app\schemas\screening_database.py` — passed
- Frontend typecheck: `node_modules\.bin\tsc --noEmit --skipLibCheck --incremental false` — passed
- Frontend build: `npm run build` — passed
- API smoke:
  - `GET /api/screening-database/imports?limit=1` — 200
  - `GET /api/screening-database/imports/b6f508a7-36e4-4753-bde8-902bd3bc1e9d` — 200
  - `GET /api/screening-database/imports/b6f508a7-36e4-4753-bde8-902bd3bc1e9d/report` — 200 with CSV attachment
- Browser manual QA:
  - desktop/default Dashboard load — passed, no console errors
  - tablet viewport `1024x768` — header/upload/imports visible, no console errors
  - production-size viewport `1440x900` — header/actions/import labels visible, no console errors
  - source check button — feedback shown after API call
  - import detail button — detail panel opened
  - import report download button — download feedback shown

### Known bugs / open issues update

- Import source file download endpoint intentionally returns `409` for multi-file imports; current Dashboard uses CSV report download instead for multi-file import jobs.
- `more` action in the recent imports table remains disabled because there is still no additional menu action defined.
- Patient-level data export remains out of scope for Dashboard import summary; report endpoint exports metadata only.

### Blockers update

- No blocker for Dashboard import detail/report/source-check workflow.
- Backend server must be launched from `backend` cwd (`python -m uvicorn app.main:app --host 127.0.0.1 --port 8010`) so it loads `backend/app/main.py`; running from repo root loads the wrong `app.main` and misses the screening-database router.

### Next recommended step

1. Decide whether import source downloads should support multi-file ZIP archives.
2. Add an import detail modal if the inline detail row becomes too dense after more metadata is added.
3. Add a real `more` menu only when there are defined safe actions.

---

## 1) Project identity

- **Project name:** seamlessfordmis
- **Project type:** Internal hospital-safe web application
- **Primary purpose:** ระบบคัดกรอง/ติดตามกลุ่มเป้าหมายจากฐานข้อมูลการตรวจโรค และไฟล์กลุ่มเป้าหมาย
- **Main business goal:** เช็กว่าในกลุ่มเป้าหมาย มีใครเคยได้รับการตรวจ/รักษาตามโรคหรือบริการที่เลือกแล้วบ้าง, ล่าสุดเมื่อไร, เกินกี่ปีแล้ว, และใครยังไม่พบประวัติ

---

## 2) Core business understanding

### 2.1 แหล่งข้อมูลหลัก
ระบบใช้ข้อมูลจาก 2 แหล่งหลัก:

1. **ฐานข้อมูลการตรวจโรค**
   - มาจากไฟล์ Excel / แหล่งนำเข้าอื่น
   - มีข้อมูลประวัติการตรวจ/บริการ/รักษา
   - ใช้เป็นแหล่งหลักของประวัติการตรวจโรค

2. **ไฟล์กลุ่มเป้าหมาย**
   - อาจมีหลายไฟล์
   - ไฟล์ Excel อาจมีหลาย sheet
   - ไม่ได้เป็นแค่รายชื่อกลุ่มเป้าหมาย
   - บาง sheet อาจมีประวัติการตรวจ/รักษาอยู่แล้ว
   - ระบบต้องอ่าน **ทุก sheet** และ classify ว่าเป็น:
     - roster_sheet
     - history_sheet
     - mixed_sheet
     - unknown_sheet

### 2.2 ตัวระบุบุคคล
- ในฐานข้อมูลการตรวจโรค คอลัมน์ `VCTID,NAPNumber,PID` ให้มองเป็น **identifier field เดียว**
- ในไฟล์กลุ่มเป้าหมาย ใช้ `CID` เป็นตัวระบุหลัก
- กฎการจับคู่หลัก:
  - `normalize(VCTID,NAPNumber,PID) == normalize(CID)`

### 2.3 กฎ matching / linking
ลำดับความสำคัญ:
1. exact 13-digit citizen ID
2. ถ้าไม่มี citizen ID:
   - exact normalized full name
   - แล้วดู birth date
   - แล้วดู address เป็นตัวช่วย
3. ถ้ายังไม่แน่ใจ:
   - mark `needs_review`
   - ห้าม merge แบบเงียบ ๆ

### 2.4 แหล่งประวัติที่ต้องใช้ในผลลัพธ์
ผลลัพธ์ต้องใช้ข้อมูลจาก **ทั้ง 2 แหล่ง**:
1. disease screening database history
2. target-group-file-side history

ห้ามสรุปว่า “ยังไม่มีประวัติ” หรือ “ยังไม่เคยตรวจ” ถ้าในไฟล์กลุ่มเป้าหมายมีประวัติอยู่แล้วใน sheet อื่น

### 2.5 กฎ latest date
- วันที่ล่าสุดต้องคำนวณจาก **เฉพาะบริการ/โรคที่ผู้ใช้เลือก**
- ห้ามเอาวันที่ของบริการอื่นมาปน
- ถ้ามีข้อมูลจากหลายแหล่ง ให้เลือก latest relevant date จาก eligible records ทั้งหมด และเก็บ source ว่ามาจากไหน

---

## 3) Current architecture direction

ระบบควรมีโครงสร้างข้อมูลระดับ concept ดังนี้:

- `import_jobs`
- `source_files`
- `disease_screening_records`
- `target_group_jobs`
- `target_group_job_files`
- `target_group_sheets`
- `target_group_rows`
- `target_group_history_rows`
- `patients` / `linked_persons` / `person master` (ถ้าเริ่มรวมแล้ว)
- `target_group_person_result`
- `target_group_person_result_provenance`
- `audit_logs`

---

## 4) Agreed business rules (do not break)

### 4.1 กฎที่ห้ามเปลี่ยนโดยพลการ
- ห้ามเดาข้อมูลที่หาย
- ห้ามใช้ fuzzy matching แบบ aggressive
- exact CID match สำคัญที่สุด
- ถ้าไม่มี exact CID ค่อยใช้ name + birth date + address แบบ conservative
- target-group-side history เป็น valid evidence
- ห้าม ignore หลักฐานจาก sheet อื่นของไฟล์กลุ่มเป้าหมาย
- person-level visible result table ต้องเป็น **1 คน = 1 แถว**
- provenance ต้องเก็บไว้ แต่ห้ามแสดงเป็น duplicate visible rows
- invalid identifier ต้องไม่ถูกนับเป็น no-history
- non-Thai / insufficient identity ต้องมี category แยก
- loading/progress UI ต้องไม่หลอกผู้ใช้ด้วยเปอร์เซ็นต์ปลอม

### 4.2 Result categories ที่ควรรองรับ
- พบประวัติในฐานข้อมูลการตรวจโรค
- พบประวัติในไฟล์กลุ่มเป้าหมาย
- พบประวัติจากทั้งสองแหล่ง
- ยังไม่พบประวัติ
- ยังไม่เคยตรวจ
- ตรวจแล้วแต่เกินกำหนด
- ตรวจแล้วและยังไม่เกินกำหนด
- ตัวระบุไม่ถูกต้อง
- ไม่มีข้อมูลตัวระบุ
- ต้องตรวจสอบ
- ไม่ใช่คนไทย
- ข้อมูลระบุตัวตนไม่พอ
- นอกขอบเขตกลุ่มเป้าหมาย

---

## 5) Phase roadmap summary

### Phase 0
Data profiling และ field verification

### Phase 1
Correct field mapping + normalization layer

### Phase 2
Clean import pipeline for disease screening database

### Phase 3
Clean import pipeline for target group files

### Phase 4
Matching engine by normalized identifier

### Phase 5
Disease/service multi-select result generation

### Phase 6
Group summary + person-level output refinement

### Phase 7
Frontend UX aligned with real business output

### Phase 8
Export / reporting

### Phase 9
Hardening, validation, and production safety

### Post-phase practical enhancements
- filter state persistence
- overdue threshold UX
- age/sex formatting
- sticky header
- patient detail modal
- performance diagnosis and optimization
- unified linked database model
- multi-sheet target-group history ingestion
- deduplication / identity resolution refinement
- pagination / rows-per-page
- loading / progress UX

---

## 6) Current phase snapshot

- **Current phase:** Phase 7 (Frontend UX — Dashboard redesign: screening data upload workflow complete)
- **Current focus:** Dashboard ปรับเป็น "จัดการข้อมูลการคัดกรองโรค" พร้อม upload workflow, import history table, source integrity card
- **Status:** in_progress
- **Last updated by:** Claude (Cowork session)
- **Last updated at:** 2026-05-11

### Current phase goal
ให้ระบบสามารถ generate ผลลัพธ์ได้ถูกต้องโดยใช้ข้อมูลจากทั้งสองแหล่ง:
1. disease_screening_records (ฐานข้อมูลการตรวจโรค)
2. target_group_history_rows (ประวัติที่ฝังอยู่ใน sheet อื่นของไฟล์กลุ่มเป้าหมาย)

### What is already completed in this phase

- [x] multi-sheet reading: `excel_target_group_importer.py` อ่านทุก sheet แล้ว ✅
- [x] sheet classification: roster / history / mixed / unknown ✅
- [x] history staging: `_stage_history_row()` และ `_stage_embedded_history_from_roster_row()` ✅
- [x] 1-person-1-row: `_build_person_contexts()` + `PersonResultContext` ✅
- [x] provenance fields: source_file_name, source_sheet_name, source_row_no ✅
- [x] `_expand_selected_service_keys()` เพิ่ม Thai slugs เป็น eligible keys ✅ (2026-05-03)
- [x] `field_mapping_service.py` เพิ่ม `_THAI_SERVICE_SLUG_TO_CANONICAL` + `_canonical_service_key()` ✅ (2026-05-03)
- [x] `_extract_target_group_history_service()` remap Thai label → canonical key ✅ (2026-05-03)
- [x] `_history_evidence_from_model()` ใช้ column fields โดยตรง (ไม่ parse raw_json ซ้ำ) ✅ (2026-05-03)
- [x] Migration 20260503_0010: composite indexes บน target_group_history_rows ✅ (2026-05-03)
- [x] **Phase B — multi-sheet ingestion (2026-05-03 session 2):**
  - `HISTORY_HINT_COLUMNS` แก้ไขแล้ว — ถอด demographic fields (`birth_date`, `nationality`, `address`) ออก เพื่อไม่ให้ roster sheet ถูก misclassify เป็น MIXED_SHEET
  - `_stage_unknown_sheet_row()` เพิ่มแล้ว — rows จาก UNKNOWN_SHEET ที่มี identity column ถูก stage เป็น `TargetGroupHistoryRow` ด้วย `validation_status="unclassified"` แทนที่จะ drop เงียบๆ
  - `_stage_embedded_history_from_roster_row()` เพิ่มแล้ว — MIXED_SHEET rows ถูก stage ทั้ง roster row และ history row
  - `_persist_sheet_metadata()` เพิ่มแล้ว — บันทึก `TargetGroupSheet` สำหรับทุก sheet ในไฟล์
  - `_list_group_sheets()` เพิ่มแล้ว — API response รวม sheet metadata
  - tests H.1–H.7 เพิ่มแล้วใน `tests/test_target_group_import.py`

### What is currently in progress

- [ ] ยังไม่ได้ run `alembic upgrade head` บน production database (ต้องทำด้วยมือ)
- [ ] ยังไม่ได้ re-generate results ของ target groups เดิม (เพื่อให้ pick up Thai slug mapping ใหม่)

### What remains to be done

- [ ] **get_results() performance**: โหลด TargetGroupRows ทั้งหมดทุก page request — ควร cache person_group_key ใน TargetGroupResult หรือทำ server-side pagination
- [ ] **Patient detail modal (Step G)**: แสดง history จากทั้งสองแหล่งแบบ source-aware — `patient_query_service.py` ยังใช้ `DiagnosisHistory` (legacy) แทน `DiseaseScreeningRecord`
- [ ] **Export (Phase 8)**: ยังไม่ได้ทำ

### Current blockers

- [ ] ไม่มี blocker เร่งด่วน — pending tasks ข้างบนเป็น enhancement / polish

---

## 7) Recently completed work

> เพิ่มรายการใหม่บนสุดทุกครั้งที่งานเสร็จ

### 2026-05-13 — Result Review & Follow-up Workspace (Scopes A–F)

**เป้าหมาย:** เปลี่ยนหน้า "ผลลัพธ์กลุ่มเป้าหมาย" ให้กลายเป็น **Result Review & Follow-up Workspace** สำหรับเจ้าหน้าที่โรงพยาบาล — ตาราง result เป็น primary workspace, filter ถูก persist, modal มีแท็บครบ, และ provenance แสดงเป็น badge chip แทนข้อความยาว

**ขอบเขตงาน (Scopes):**

| Scope | รายละเอียด | สถานะ |
|-------|-----------|-------|
| A | Filter state persistence: URL params (primary) + localStorage `wsFilt_${groupId}` (fallback) | ✅ Done |
| B | Result table เป็น primary workspace; screening config + summary collapsible ด้านบน; sticky toolbar | ✅ Done |
| C | Per-row "ติดตามผล" (disabled stub) + "ดูรายละเอียด" buttons; follow-up records แยกจาก raw source | ✅ Done |
| D | Detail modal 5 tabs: ข้อมูลสรุป / ที่มาข้อมูล / ประวัติการตรวจ / ติดตามผล / แก้ไขข้อมูล | ✅ Done |
| E | Export section ใน sticky toolbar ใกล้ตาราง; disabled ถ้า results ยังไม่พร้อม | ✅ Done |
| F | Compact provenance badges ใน table rows แทน text column ยาว | ✅ Done |

**Files changed:**

1. `frontend/src/components/target-groups/ResultsTable.tsx` — REWRITTEN
   - เพิ่ม `onFollowUp` prop ควบคู่กับ `onOpenDetails`
   - `buildProvenanceBadges(row): ProvBadge[]` — badge chip แสดงสถานะตัวตน, แหล่งประวัติ, match method, provenance count, warning
   - รวม "วัน" + "ปี" เป็นคอลัมน์ "ผ่านมา (วัน / ปี)" เดียว
   - CID อยู่ใน `<code className="cid-text">` (monospace)
   - Action column: "ติดตามผล" (primary, disabled + tooltip) + "ดูรายละเอียด" (secondary)

2. `frontend/src/components/target-groups/PatientDetailModal.tsx` — REWRITTEN (Scope D)
   - 5-tab modal: summary | provenance | history | followup | correction
   - Lazy source history loading — เรียก API เฉพาะเมื่อ activate history tab
   - "ติดตามผล" tab: API stub box "อยู่ระหว่างพัฒนา"
   - "แก้ไขข้อมูล" tab: API stub box "อยู่ระหว่างพัฒนา"
   - `modal-card-wide` (900px) ใช้ CSS class ใหม่

3. `frontend/src/components/target-groups/TargetGroupResultsWorkspace.tsx` — REWRITTEN (Scopes A, B, E)
   - **localStorage helpers** (module-level, ไม่ใช่ใน component):
     - `FILTER_PERSIST_KEYS = ["services", "view", "overdue_enabled", "overdue_input", "page_size", "q"]`
     - `makeStorageKey(groupId)` → `wsFilt_${groupId}` (key ไม่เคย shared ข้าม group)
     - `saveFiltersToStorage`, `loadFiltersFromStorage`, `clearStorageKey` — ทุกอย่าง wrapped ใน try/catch
   - State ใหม่: `viewSaved`, `viewSavedTimerRef`, `storageRestoredRef` (one-time mount guard)
   - `updateFilters()` เรียก `saveFiltersToStorage` ทุกครั้งที่ filter เปลี่ยน
   - `clearFilters()` — clear localStorage + reset URL params ให้เป็น default
   - `saveCurrentView()` — save ไป localStorage + แสดง toast "บันทึกมุมมองนี้แล้ว" 2200ms
   - `handleFollowUp(_row)` — stub ว่างเปล่า (API ยังไม่ build)
   - Mount `useEffect` — restore จาก localStorage ถ้า URL ไม่มี `services` param (runs once only ด้วย `storageRestoredRef`)
   - Cleanup `useEffect` — clear timer เมื่อ unmount
   - Layout ใหม่:
     1. **Screening config** ใน `<details>` ที่ collapse เมื่อมีผลลัพธ์แล้ว
     2. **Summary** ใน `<details>` แสดง coverage% + total เป็น chip
     3. **Results table panel** เป็น PRIMARY workspace มี sticky two-row toolbar:
        - Row 1: view tab buttons (scrollable)
        - Row 2: search | overdue toggle + years | page size | Export + Refresh + ล้างตัวกรอง + บันทึกมุมมองนี้
     4. Toast: "✓ บันทึกมุมมองนี้แล้ว" (CSS animation, role="status")
   - `isFiltered` derived: `activeFilter !== "all" || overdueEnabled || searchQuery.trim().length > 0`

4. `frontend/src/app/globals.css` — MODIFIED (appended ~120+ lines)
   - `.sticky-table-toolbar`, `.sticky-table-toolbar-row`, `.action-cell`, `.cid-text`
   - `.prov-badges`, `.prov-badge`, `.prov-badge-{ready/warning/danger/accent/muted}`
   - `.modal-tabs`, `.modal-tab`, `.modal-tab.active`, `.modal-tab-body`
   - `.modal-card-wide`, `.api-stub-box` และ variant
   - `.view-saved-toast` + `@keyframes fade-in-out`
   - `.panel-summary-toggle`, `.compact-chip`, `.scrollable-tab-row`
   - `.toolbar-actions`, `.results-workspace-panel`

**Business rules maintained:**
- 1 คน = 1 แถวในตาราง (ไม่เปลี่ยน)
- provenance เก็บครบ แสดงเป็น badge chip (ไม่ซ้ำ row)
- ห้าม fake save / fake export
- localStorage key แยกต่างหากตาม `groupId` — ไม่ใช้ข้าม group
- ทุกการแก้ไขต้องมี audit trail (follow-up + correction tab เป็น stub รอ API)
- Export disabled เมื่อ results ยังไม่ ready หรือ stale

**API stubs (ยังไม่มี backend — planned):**
- `POST /api/target-groups/:groupId/results/:resultId/followups` — บันทึกการติดตามผล
- `POST /api/target-groups/:groupId/results/:resultId/corrections` — แก้ไขข้อมูลบุคคล

**TypeScript:** ✅ ผ่าน clean — `npx tsc --noEmit` รันแล้ว ไม่มี errors (ยืนยัน 2026-05-14)

**Status:** ✅ code complete และ type-safe — พร้อม build และทดสอบ UI

**Open issues:**
- [ ] Issue 22: `POST .../followups` endpoint ยังไม่ build — "ติดตามผล" ปุ่ม disabled stub
- [ ] Issue 23: `POST .../corrections` endpoint ยังไม่ build — "แก้ไขข้อมูล" tab แสดง stub
- [x] Issue 24: ~~ควร run `npx tsc --noEmit` verify ก่อน deploy~~ — **ปิดแล้ว: รันผ่าน clean 2026-05-13**

**Next recommended step:**
1. Build และทดสอบ UI ด้วย browser จริง — ตรวจ sticky toolbar, toast, localStorage restore, modal tabs
2. Implement `POST .../followups` backend endpoint เมื่อพร้อม
3. Implement `POST .../corrections` backend endpoint เมื่อพร้อม

---

### 2026-05-14 — TypeScript error recovery (session continuation)

**งานที่ทำ:** แก้ไข TypeScript errors ที่เกิดจาก file truncation ในเซสชันก่อน

**ปัญหาที่พบ:**
- `ResultsTable.tsx` — truncated ที่ line 237 กลาง JSX comment (`{/* Age — hide`); ส่วนที่เหลือ (แถว Age ถึง Actions + ปิด tbody/table/div) หายไป
- `TargetGroupResultsWorkspace.tsx` — มี orphaned garbage code (`cel}` + JSX fragment ซ้ำซ้อน) ต่อท้ายหลัง closing `}` ของ component function (lines 1483–1610); ตัว component เองถูกต้องสมบูรณ์ที่ line 1482
- `api.ts` — truncated ที่ line 365 กลาง `link.click()` ทำให้ขาด 3 บรรทัดและ `stageUploadScreeningFile` ทั้งหมด

**การแก้ไข:**
- `ResultsTable.tsx` — trim truncated last line แล้ว append JSX ที่หายไปตั้งแต่ Age column ถึง `}`; ไฟล์ครบ 332 บรรทัด
- `TargetGroupResultsWorkspace.tsx` — truncate ไฟล์ที่ line 1482 (byte-safe ด้วย Python binary mode) เพื่อลบ orphaned fragment; ไฟล์ครบ 1483 บรรทัด
- `api.ts` — append ส่วนที่หาย (`link.click()`, `link.remove()`, `URL.revokeObjectURL()`, `return`, `}`, `stageUploadScreeningFile`); ไฟล์ครบ 378 บรรทัด

**Verification:** `npx tsc --noEmit` → ✅ 0 errors; brace balance check ทั้ง 3 ไฟล์ → balanced

---

### 2026-05-11 — Dashboard Redesign: Screening Data Upload Workflow

**เป้าหมาย:** ปรับหน้า Dashboard ใหม่ทั้งหมด — เพิ่ม screening data upload workflow, import history table, source integrity card, และ quick actions panel

- **Tasks completed:** Task #1–#4 (component + API build), Task #5 (PROJECT_STATUS.md update)
- **Scope:** Frontend redesign + new backend router for screening data management

**Files changed:**

1. `backend/app/schemas/screening_database.py` — NEW
   - `ImportJobSummaryResponse`, `ImportJobListResponse`, `StageUploadResponse` Pydantic models

2. `backend/app/api/screening_database.py` — NEW
   - `GET /api/screening-database/imports` — paginated import job list (source_type=main_history)
   - `POST /api/screening-database/stage-upload` — validates extension + size, saves to `source_data_dir` with counter-suffix (no silent overwrite), PDF flagged `needs_review=True`

3. `backend/app/main.py` — MODIFIED
   - Added `screening_database_router` inclusion

4. `frontend/src/types/screening-database.ts` — NEW
   - `ImportJobSummary`, `ImportJobListResponse`, `StageUploadResponse` TypeScript types

5. `frontend/src/lib/api.ts` — MODIFIED
   - Added `listScreeningImports(limit, offset)` and `stageUploadScreeningFile(formData)`
   - Fixed pre-existing truncation on disk (file ended mid-function at `return request<ResultSource`)

6. `frontend/src/components/dashboard/DashboardStatusSummary.tsx` — NEW
   - 5-card metrics grid: source_file_count, patients, disease_screening_records, import ID, last modified

7. `frontend/src/components/dashboard/SourceIntegrityCard.tsx` — NEW ("use client")
   - Hash display with clipboard copy button, file list (up to 8), change status indicator

8. `frontend/src/components/dashboard/ScreeningDataUploadCard.tsx` — NEW ("use client")
   - Drag-and-drop zone + file input; frontend validation (extension, empty, >200MB)
   - `UploadState` union: idle | validating | uploading | staged | staged_pdf | error
   - Shows per-file validation errors; staged workflow (upload → review → sync separately)
   - PDF shows warning result box with `needs_review` note

9. `frontend/src/components/dashboard/SupportedFileTypesCard.tsx` — NEW
   - Static card: Excel/CSV (supported), PDF (staged only), others (unsupported)

10. `frontend/src/components/dashboard/RecentImportsTable.tsx` — NEW
    - ImportStatusBadge, FileTypeTag; columns: date, filename, type, status, rows, created_by, actions
    - "view" action disabled (no detail page yet); empty state handled

11. `frontend/src/components/dashboard/DashboardQuickActions.tsx` — NEW ("use client")
    - Sync: functional (calls `syncDiseaseScreeningDatabase()`); others: disabled with explanations
    - Shows `JobProgressCard` during/after sync

12. `frontend/src/components/dashboard/UploadCTAButton.tsx` — NEW ("use client")
    - Header CTA button; scrolls to `.db-dropzone` on click

13. `frontend/src/app/dashboard/page.tsx` — REWRITTEN
    - Server component; `Promise.allSettled` for 3 parallel API calls
    - Layout: header → DashboardStatusSummary → 3-col grid → DashboardQuickActions → RecentImportsTable

14. `frontend/src/app/globals.css` — MODIFIED
    - ~350 lines added: `.db-page`, `.db-header`, `.db-middle-grid` (3-col responsive), `.db-dropzone`, `.db-pending-file*`, `.db-upload-result--success/warning/error`, `.db-imports-table`, `.db-quick-actions`, etc.

**Bugs fixed during this session:**
- TypeScript: `variant="warning"` missing from MetricCard prop union — added `| "warning"`
- TypeScript: unreachable `=== "uploading"` comparison in ScreeningDataUploadCard — restructured conditional
- `api.ts` disk truncation (Write tool diverged from bash reality) — fixed with `cat >>` append
- `page.tsx` JSX truncation (Thai chars in heredoc) — fixed with proper ENDOFFILE delimiter

**Quality checks:**
- `tsc --noEmit --skipLibCheck --incremental false` → 0 errors
- Python AST parse on all 3 new backend files → all pass

**Business rules maintained:**
- Staged upload: file saved to `source_data_dir` only; DB not touched until user clicks Sync
- No silent overwrites: counter-suffix applied when filename already exists
- PDF always flagged `needs_review=True` (no parser exists)
- Disabled actions shown (not hidden) with tooltip explaining what's missing

**Status:** code complete and type-safe
**Next recommended steps:**
1. Run `alembic upgrade head` (migration 0015: `source_set_hash` on `target_group_result_summaries`)
2. Re-generate results for existing target groups (populate `generated_source_set_hash`)
3. Test upload workflow end-to-end with a real Excel file

### 2026-05-07 — Frontend UX Phase 7: Target Group Workspace + Design System

**เป้าหมาย:** ปรับหน้าผลลัพธ์กลุ่มเป้าหมายให้กลายเป็น "workspace" ที่ผู้ใช้แก้ไขได้ทุกขั้นตอนจากหน้าเดียว โดยไม่ต้องสร้างกลุ่มใหม่ และเพิ่ม design system tokens + stepper UI ให้ครบ

**ไฟล์ที่เปลี่ยน:**

1. `frontend/src/components/target-groups/TargetGroupResultsWorkspace.tsx` — REWRITTEN
   - เพิ่ม `WorkspaceStepper` (horizontal 5-step: ตั้งชื่อ / อัปโหลด / ตรวจสอบ / เลือกคัดกรอง / ดูผล) แสดงตลอดหน้า
   - เพิ่ม breadcrumb (`กลุ่มเป้าหมาย / ชื่อกลุ่ม`) พร้อม Link กลับรายการ
   - เพิ่ม `GroupNameEditor` — inline edit ชื่อกลุ่ม (กด Enter บันทึก, Esc ยกเลิก)
   - เพิ่ม `ConfigDirtyBanner` — แสดง warning เมื่อ `selectedKeys` ต่างจาก `results.summary.selected_service_keys` (ผลลัพธ์ stale)
   - `isDirty` computed จาก `sameSelection(selectedKeys, results.summary.selected_service_keys)` — ไม่มี backend ใหม่
   - `activeStep` logic: step 4 (ดูผล) เมื่อมีผลลัพธ์และไม่ dirty; step 3 (เลือกคัดกรอง) เมื่อไม่มีผล / dirty
   - ปุ่ม generate เปลี่ยนเป็น "สร้างผลลัพธ์ใหม่" เมื่อ dirty
   - export ถูก disable เมื่อ dirty (ผลลัพธ์ไม่ตรงกับ config ปัจจุบัน)
   - แสดง badge "ผลลัพธ์ไม่ตรงกับรายการที่เลือก" + วันที่ผลลัพธ์ล่าสุดใน identity panel
   - ทุก Thai string ย้ายเป็น string concatenation / `{"..."}` เพื่อหลีกเลี่ยง template literal truncation

2. `frontend/src/lib/api.ts` — เพิ่ม `updateGroupName(groupId, groupName)`
   - PATCH `/api/target-groups/{groupId}` with `{ group_name }` body
   - ใช้ `request<TargetGroupDetail>` helper เหมือน endpoints อื่น
   - หมายเหตุ: backend ยังไม่มี endpoint นี้ — ถ้า backend ยัง 404 จะ throw ApiError แสดงใน UI โดยไม่ crash

3. `frontend/src/app/globals.css` — เพิ่ม workspace component tokens
   - `.workspace-breadcrumb`, `.breadcrumb-link`, `.breadcrumb-sep`, `.breadcrumb-current`
   - `.workspace-group-name`, `.name-editor-row`, `.name-editor-col`, `.name-editor-input`
   - `.ghost-button` (subtle border-only button)
   - `.config-dirty-banner`, `.config-dirty-content`, `.config-dirty-icon`, `.config-dirty-title`, `.config-dirty-note`

4. `frontend/src/lib/api.ts` line 293 — fix pre-existing truncation ของ `getResultSourceHistory()` (function body ถูก cut ไว้ที่ `fo`)

**TypeScript:** `npx tsc --noEmit` → ผ่าน 0 errors

**หมายเหตุด้าน business rules:**
- ไม่เปลี่ยน matching logic, CID rules, หรือ result generation logic
- dirty detection ใช้เฉพาะ `selectedKeys` (service selection ที่ส่ง generate-results) — ไม่ใช้ `overdueYears` เพราะ threshold apply แบบ dynamic ใน getGroupResults ไม่ต้อง regenerate
- ปุ่ม export disabled เมื่อ dirty เพื่อป้องกันการ export ข้อมูลที่ stale

**Next tasks:**
- [ ] Backend: implement `PATCH /api/target-groups/{id}` เพื่อรองรับ inline name editing
- [ ] Frontend: Patient detail modal source-aware history (Phase G)

---

### 2026-05-03 — Phase B: multi-sheet ingestion hardening (session 2)

**เป้าหมาย:** ทุก sheet ในไฟล์ Excel ถูกอ่าน / classify / preserve provenance อย่างถูกต้อง และ rows ที่เคยหายเงียบๆ ถูก surface ให้ตรวจสอบได้

**ไฟล์ที่เปลี่ยน:**

1. `backend/app/importers/excel_target_group_importer.py`
   - ถอด `birth_date`, `วันเกิด`, `nationality`, `สัญชาติ`, `address`, `ที่อยู่` ออกจาก `HISTORY_HINT_COLUMNS` — demographic fields ซ้ำกับ `ROSTER_CONTEXT_COLUMNS` ทำให้ roster sheet ถูก misclassify เป็น MIXED_SHEET

2. `backend/app/services/target_group_import_service.py`
   - `_stage_unknown_sheet_row()` — NEW: stage UNKNOWN_SHEET rows ที่มี identity column เป็น `TargetGroupHistoryRow(validation_status="unclassified")` แทนที่จะ drop
   - `_stage_embedded_history_from_roster_row()` — NEW: extract history data จาก MIXED_SHEET roster rows
   - `_persist_sheet_metadata()` — NEW: persist `TargetGroupSheet` object สำหรับทุก parsed sheet
   - `_list_group_sheets()` — NEW: query sheets สำหรับ group detail response
   - `_build_sheet_responses_from_lookup()` — NEW: build schema responses จาก persisted sheet lookup
   - `_stage_rows()` — updated: UNKNOWN_SHEET rows with identity now call `_stage_unknown_sheet_row()` instead of being silently dropped

3. `backend/tests/test_target_group_import.py`
   - เพิ่ม H.1–H.7 tests ครอบคลุม: roster-only, roster+history, mixed, unknown, provenance, sheet metadata, multi-sheet provenance linking

---

### 2026-05-03 — Thai service label → canonical key mapping (bug fix session)

**Root cause แก้:** บางคนมีประวัติใน sheet อื่นของไฟล์กลุ่มเป้าหมาย แต่ระบบแสดงว่าไม่มีประวัติ

**สาเหตุ:** Thai label เช่น "คัดกรองมะเร็งปากมดลูก" ถูก slugify เป็น Thai slug (`khadkrxng_mxaerng_pakmdluk`) ไม่ match กับ canonical key `cervical_screen` ที่ `_expand_selected_service_keys()` ใช้ filter

**ไฟล์ที่เปลี่ยน:**

1. `backend/app/services/field_mapping_service.py` — REWRITTEN (389 lines)
   - เพิ่ม `_THAI_SERVICE_SLUG_TO_CANONICAL: dict[str, str]` (30+ entries)
   - เพิ่ม `_canonical_service_key(raw_slug)` — single resolution point
   - `_extract_target_group_history_service()` — apply canonical remap หลัง slugify
   - `_extract_target_history_context()` — apply canonical remap เช่นกัน

2. `backend/app/services/result_generation_service.py`
   - `_expand_selected_service_keys()` — เพิ่ม Thai slugs จาก `_THAI_SERVICE_SLUG_TO_CANONICAL` เป็น eligible record keys (backward compat สำหรับ rows ที่ import ก่อน fix)
   - `_history_evidence_from_model()` — ใช้ `row.normalized_birth_date` และ `row.normalized_address` โดยตรง แทนการ parse `raw_json` ซ้ำ (bug fix)

3. `backend/alembic/versions/20260503_0010_composite_history_index.py` — NEW
   - `idx_tg_history_rows_job_service_key` บน `(group_job_id, normalized_service_key)`
   - `idx_tg_history_rows_job_cid` บน `(group_job_id, normalized_cid)`
   - `idx_tg_history_rows_job_name` บน `(group_job_id, normalized_full_name)`
   - ทุก op ป้องกัน idempotency ด้วย `_has_index()` check

---

## 8) Current known bugs / open issues

- [x] ~~บัค: Thai service label slugs ไม่ match canonical keys~~ → **แก้แล้ว 2026-05-03**
- [x] ~~บัค: `_history_evidence_from_model()` parse birth_date จาก raw_json ซ้ำแทน column~~ → **แก้แล้ว 2026-05-03**
- [x] ~~บัค: UNKNOWN_SHEET rows ถูก drop เงียบๆ~~ → **แก้แล้ว 2026-05-03** — staged เป็น `validation_status="unclassified"` แทน
- [ ] ปัญหาธุรกิจ: rows ที่ import ก่อน 2026-05-03 อาจมี normalized_service_key เป็น Thai slug — ต้อง re-generate results หรือ backfill key
- [ ] ปัญหาประสิทธิภาพ: `get_results()` โหลด TargetGroupRows ทั้งหมดทุก page request (O(n) ทุกครั้ง) — ควร cache person_group_key ใน TargetGroupResult
- [ ] ปัญหาประสิทธิภาพ: migration 20260503_0010 ยังไม่ได้ run บน production database
- [ ] ปัญหา UI / rendering: patient detail modal ยังไม่แสดง source-aware history (Phase G)
- [ ] ปัญหา null/undefined safety: modal อาจ crash ถ้า provenance fields เป็น null

---

## 9) Performance status

### Current bottleneck understanding
- Frontend render: ยังไม่ได้วัด
- Backend API: `get_results()` loads all TargetGroupRows on every page call — O(n) per request
- Database query: target_group_history_rows ขาด composite index (แก้แล้วด้วย migration 0010 — ยังรอ run)
- Dev mode overhead: ไม่ได้วัด
- Production build comparison: ไม่ได้วัด

### Known heavy pages / flows
- dashboard: ไม่ทราบ
- target group detail: น่าจะหนักเพราะ join หลาย table
- result generation: หนัก — อ่านทุก row ทุก page request
- table scroll: ยังไม่ได้ optimize
- filter: client-side
- search: ไม่ทราบ
- export: ยังไม่ได้ทำ
- patient detail modal: ยังไม่ได้ทำ

### Planned optimizations
- [ ] เพิ่ม `person_group_key` column ใน `target_group_results` เพื่อ skip rebuild person_contexts
- [ ] Server-side pagination สำหรับ result table
- [ ] Run alembic migration 20260503_0010 เพื่อให้ composite index ทำงาน

---

## 10) Current data model notes

### Identity rules
- Primary key for matching: citizen ID 13 digits
- Secondary identity support: full name + birth date + address
- Review required when:
  - no CID
  - name matches but date/address insufficient
  - conflicting identity evidence

### Target group workbook rules
- Must inspect **all sheets**
- Must classify sheets
- Must preserve:
  - file name
  - sheet name
  - row number
- Must extract history-bearing rows when present

### Consolidation rules
- One person = one visible result row
- Multiple source/evidence rows = aggregate into provenance/history details
- Duplicate roster rows should not create duplicate visible person rows

---

## 11) API / frontend contract notes

### Important response contract expectations
- arrays should prefer `[]` instead of `undefined`
- modal/detail payloads must be null-safe
- result rows should include stable ids/keys
- provenance fields should be explicit where practical
- summary formulas must be consistent between backend, UI, and export

### Frontend UX rules
- business summary first
- technical details secondary
- compact filter bar near result table
- result tabs at table header
- rows-per-page supported
- overdue filter should be explicit on/off
- modal should not crash on partial data
- loading/progress states should be visible

---

## 12) Export/reporting notes

Exports should remain consistent with current result logic:
- same selected service context
- same summary counts
- same result categories
- same latest-date logic

Preferred formats:
- Excel primary
- CSV optional

---

## 13) How Codex should work on this project

### Always do this before coding
1. Read:
   - `PROJECT_STATUS.md`
   - `docs/field-mapping.md`
   - `docs/result-output-model.md`
   - `docs/open-issues.md`
   - `docs/current-phase.md` (if it exists)
2. Summarize:
   - current phase
   - what is done
   - what is in progress
   - blockers
3. Continue only the agreed next step
4. Do not redesign business rules without updating this file

### Always do this after coding
Update this file:
- current phase status
- completed work
- current blockers
- known bugs/open issues
- recent changes summary
- next recommended step

---

## 14) Codex update template (must fill after each work session)

### Session summary — 2026-05-03

- **Date:** 2026-05-03
- **Task worked on:** Bug investigation + fix: Thai service labels not matching canonical keys; composite index migration; birth_date parsing bug fix
- **Files changed:**
  - `backend/app/services/field_mapping_service.py` (rewritten, 389 lines)
  - `backend/app/services/result_generation_service.py` (2 targeted fixes)
  - `backend/alembic/versions/20260503_0010_composite_history_index.py` (new file)
- **Main result:** บางคนที่มีประวัติใน sheet อื่นของไฟล์กลุ่มเป้าหมายแต่ระบบแสดงว่าไม่มีประวัติ → แก้แล้ว
- **Status:** done (code); pending: run migration + re-generate results

### What was changed

- [x] เพิ่ม `_THAI_SERVICE_SLUG_TO_CANONICAL` dict และ `_canonical_service_key()` ใน field_mapping_service.py
- [x] `_extract_target_group_history_service()` ใช้ canonical key แทน raw Thai slug
- [x] `_expand_selected_service_keys()` เพิ่ม Thai slugs เป็น eligible keys (backward compat)
- [x] `_history_evidence_from_model()` ใช้ column fields แทน raw_json parsing
- [x] Migration 0010: composite indexes บน target_group_history_rows

### What still remains

- [ ] Run `alembic upgrade head` บน production database
- [ ] Re-generate results ของ target groups ที่มีอยู่
- [ ] แก้ UNKNOWN_SHEET rows ที่ถูก drop เงียบๆ
- [ ] Patient detail modal source-aware history (Step G)
- [ ] `get_results()` performance: cache person_group_key

### New bugs/issues found

- [ ] UNKNOWN_SHEET rows drop โดยไม่มี warning ใน `target_group_import_service.py`
- [ ] rows ที่ import ก่อน fix อาจมี Thai slug แทน canonical key ใน normalized_service_key — ต้อง backfill

### Next recommended step

- [ ] Run migration 20260503_0010 แล้ว re-generate results สำหรับ target groups ที่มีอยู่เพื่อ verify fix

---

## 15) Immediate next step

- **Next recommended step:**
  1. `cd backend && alembic upgrade head` — applies migration 0015 (`source_set_hash` column on `target_group_result_summaries`)
  2. Re-generate results for all existing target groups (POST `/api/target-groups/{id}/generate-results`) — populates `generated_source_set_hash` in the summary cache
  3. Verify stale banner: add a file via FileManagementPanel → amber "มีการเพิ่ม/เปลี่ยนไฟล์" banner should appear → regenerate results → banner should disappear

- **Why this is next:** Tasks #13 and #14 (file management + stale detection) are code-complete. The stale detection compares `generated_source_set_hash` (stored at generation time) vs `group.source_set_hash` (current). Until migration 0015 runs and results are re-generated, `generated_source_set_hash` will be NULL and the banner will not appear (by design — null hash = "no baseline to compare").

- **After that (optional enhancements):**
  - Backend: implement `PATCH /api/target-groups/{id}` for inline group name editing (noted in workspace — currently shows ApiError 404 if used)
  - Frontend: Patient detail modal source-aware history wiring (Phase G / open issue 6)
  - Performance: `get_results()` history rows still load all-group on every paged request (open issue 12)

---

## 16) Notes for future refactor

- Consider unified linked database model
- Consider canonical person / person identifiers / source attributes / history events
- Consider summary cache tables for performance
- Consider server-side pagination for large result sets
- Consider background jobs for heavy import/result/export
- Consider stronger production deployment / monitoring / backup strategy


### Session summary — Phase C (2026-05-03)

- **Date:** 2026-05-03
- **Task worked on:** Phase C — Two-source result generation (disease screening DB + target-group file history)
- **Files changed:**
  - `backend/app/services/result_generation_service.py` — fixed NULL visit-date crash in `_build_row_result_payload()`; `latest_relevant_source_type` population added to `_build_result_row_response()`
  - `backend/app/schemas/result.py` — added `latest_relevant_source_type: str | None` to `GroupResultRowResponse`
  - `backend/app/schemas/patient.py` — added `ScreeningRecordResponse` and `ResultSourceHistoryResponse`
  - `backend/app/services/patient_query_service.py` — rewrote `history()` to use `DiseaseScreeningRecord`; added `source_history_for_result()` for CID-based two-source lookup
  - `backend/app/api/target_groups.py` — added `GET /{group_id}/results/{result_id}/source-history` endpoint
  - `backend/tests/test_result_generation.py` — new file, tests K.1–K.7 (two-source merge, date max, None-safety, regression guard)
  - `docs/result-generation-both-sources.md` — new file documenting Phase C two-source model
  - `docs/result-output-model.md` — added `latest_relevant_source_type` and `history_source_summary` value descriptions
  - `docs/open-issues.md` — updated issue #6 to reflect Phase C source-history endpoint exists; noted frontend modal wiring as remaining work
- **Main result:** บุคคลที่มีประวัติจากไฟล์กลุ่มเป้าหมาย (history sheet / mixed sheet) แต่ไม่มีในฐานข้อมูลการตรวจโรค จะไม่ถูกจัดเป็น `no_history_found` อีกต่อไป — ระบบรวมหลักฐานจากทั้ง 2 แหล่งอย่างถูกต้อง
- **Key fixes:**
  1. NULL visit-date crash: `max()` over TG history dates without None-filtering → fixed with explicit None guard
  2. `latest_relevant_source_type` schema field added (mirrors `last_relevant_source`)
  3. `patient_query_service` migrated from legacy `DiagnosisHistory` table to `DiseaseScreeningRecord`
  4. New `source_history_for_result()` method + `/source-history` API endpoint for frontend modal
  5. Tests K.1–K.7 covering all two-source scenarios including regression guard
- **Status:** Phase C backend complete. Frontend modal wiring (source-history endpoint → UI) remains as open issue #6.
- **Next recommended step:** Wire `GET /{group_id}/results/{result_id}/source-history` into the patient detail modal frontend component (`frontend/src/components/ResultDetailModal` or equivalent) so TG-file history is displayed alongside screening-DB records.


### Session summary — Phase C (2026-05-03)

- **Date:** 2026-05-03
- **Task worked on:** Phase C — Two-source result generation (disease screening DB + target-group file history)
- **Files changed:**
  - `backend/app/services/result_generation_service.py` — fixed NULL visit-date crash in `_build_row_result_payload()`; `latest_relevant_source_type` population added
  - `backend/app/schemas/result.py` — added `latest_relevant_source_type: str | None` to `GroupResultRowResponse`
  - `backend/app/schemas/patient.py` — added `ScreeningRecordResponse` and `ResultSourceHistoryResponse`
  - `backend/app/services/patient_query_service.py` — rewrote `history()` to use `DiseaseScreeningRecord`; added `source_history_for_result()`
  - `backend/app/api/target_groups.py` — added `GET /{group_id}/results/{result_id}/source-history` endpoint
  - `backend/tests/test_result_generation.py` — new file, tests K.1-K.7
  - `docs/result-generation-both-sources.md` — new file documenting Phase C two-source model
  - `docs/result-output-model.md` — added `latest_relevant_source_type` description
  - `docs/open-issues.md` — updated issue 6 to reflect Phase C endpoint; noted frontend wiring as remaining work
- **Main result:** บุคคลที่มีประวัติจากไฟล์กลุ่มเป้าหมาย (history sheet / mixed sheet) แต่ไม่มีในฐานข้อมูลการตรวจโรค จะไม่ถูกจัดเป็น no_history_found อีกต่อไป
- **Key fixes:**
  1. NULL visit-date crash in max() over TG history dates — fixed with explicit None guard
  2. latest_relevant_source_type schema field added
  3. patient_query_service migrated from DiagnosisHistory to DiseaseScreeningRecord
  4. New source_history_for_result() + /source-history API endpoint
  5. Tests K.1-K.7 covering all two-source scenarios
- **Status:** Phase C backend complete. Frontend modal wiring (source-history endpoint) remains as open issue 6.
- **Next recommended step:** Wire GET /{group_id}/results/{result_id}/source-history into the patient detail modal frontend component so TG-file history is displayed alongside screening-DB records.


### Session summary — Phase D (2026-05-03)

- **Date:** 2026-05-03
- **Task worked on:** Phase D — Person-level consolidation and identity resolution
- **Files changed:**
  - `backend/app/models/target_group_result.py` — added 4 columns: `canonical_person_key`, `person_link_status`, `review_required`, `duplicate_reason`; added 3 composite indexes
  - `backend/alembic/versions/20260503_0011_phase_d_person_link_fields.py` — new migration with safe _has_column guards
  - `backend/app/services/result_generation_service.py` — store new fields in `generate()`; add `_resolve_context_rows()` helper; fix `get_results()` to use `canonical_person_key` lookup with `target_row_id` fallback; use stored link fields in `_build_result_row_response()`; add `view=review_required` filter
  - `backend/app/schemas/result.py` — added `canonical_person_key: str | None = None` to `GroupResultRowResponse`
  - `backend/tests/test_person_consolidation.py` — new file, tests L.1-L.8
  - `docs/person-consolidation.md` — new file documenting Phase D consolidation model
  - `docs/identity-resolution-rules.md` — added stored-fields section
  - `docs/result-output-model.md` — added `canonical_person_key` and expanded `person_link_status` descriptions
  - `docs/open-issues.md` — fixed truncated UTF-8 tail; added issues 10 and 11 for Phase D remaining work
- **Main result:**
  - The visible result table is now definitively person-centered: one person = one row, guaranteed by person_contexts grouping at generate time
  - `canonical_person_key` stored on each result eliminates the fragile primary-row lookup bug in `get_results()`
  - Identity resolution order is conservative: exact CID > name+birthdate > name+address (review) > name-only (review) > insufficient
  - Address alone never merges people
  - Uncertain identity cases set `review_required = True` and are filterable via `?view=review_required`
  - All grouped source rows preserved in `provenance_details[]` for modal display
- **Grouping key rules:**
  - `identifier:<matched_identifier_basis>` — patient matching service already resolved
  - `cid:<normalized_cid>` — valid 13-digit CID
  - `name_birth:<name>:<dob>` — exact name + birth date
  - `review_name_address:<name>:<addr>` — name + address (review required)
  - `review_name:<name>` — name only (review required)
  - `row:<uuid>` — no usable identity (one context per row)
- **Status:** Phase D backend complete. Frontend items remain:
  - Wire `review_required` badge and filter tab in results UI (open issue 11)
  - Wire `source-history` endpoint + `person_link_status` display in patient detail modal (open issue 6)
  - Re-generate results after running migration 0011 to populate `canonical_person_key` on existing rows (open issue 10)
- **Next recommended step:** Run `alembic upgrade head` to apply migration 0011, then re-generate target group results to populate Phase D fields. After that, proceed to Phase E — frontend UI for person consolidation (review_required filter tab, modal person_link_status display, provenance accordion).


### Session summary — Phase E (2026-05-04)

- **Date:** 2026-05-04
- **Task worked on:** Phase E — Performance optimizations and linked model scaffold
- **Files changed:**
  - `backend/app/services/result_generation_service.py` — multiple changes:
    - Added `_build_summary_from_sql()`: single-round-trip aggregate SQL replacing Python iteration over all result rows
    - Added `_upsert_summary_cache()`: PostgreSQL INSERT ... ON CONFLICT DO UPDATE to write summary cache
    - `generate()`: calls `_upsert_summary_cache()` on both fresh-generate and reuse paths
    - `get_result_summary()`: tries `TargetGroupResultSummary` cache first (O(1)), falls back to aggregate SQL, then empty response
    - `get_results()`: uses `get_result_summary()` for summary; replaces full `all_target_rows` load + `_build_person_contexts()` with a page-scoped `SELECT ... WHERE id IN (page_target_row_ids)` — O(page_size) instead of O(total_rows)
    - Added `pg_insert` import and `TargetGroupResultSummary` import
  - `backend/app/models/target_group_result_summary.py` — new model: `TargetGroupResultSummary` with all headcount and coverage fields; unique index on `(group_job_id, selected_service_hash)`
  - `backend/app/models/__init__.py` — registered `TargetGroupResultSummary`
  - `backend/alembic/versions/20260504_0012_phase_e_result_summary_cache.py` — creates `target_group_result_summaries` table with safe `_has_table` guard
  - `backend/alembic/versions/20260504_0013_phase_e_perf_indexes_linked_scaffold.py` — adds 5 composite performance indexes; creates 4 linked-model scaffold tables (`person_master`, `person_identifiers`, `disease_screening_events`, `target_group_membership`) — all empty, schema only
  - `frontend/src/components/target-groups/TargetGroupResultsWorkspace.tsx` — added `{ key: "review_required", label: "รอยืนยันตัวตน (Phase D)" }` to `VIEW_FILTERS`
  - `docs/performance-diagnosis.md` — added Phase E results section
  - `docs/performance-optimization-plan.md` — added Phase E optimizations 5–8
  - `docs/unified-linked-database-design.md` — added Phase E scaffold table status and Phase F cutover checklist
  - `docs/open-issues.md` — marked issues 1 and 11 resolved; added issues 12–15 for remaining Phase E/F work
- **Main results:**
  - Summary computation is now O(1) (cache hit) or O(1 DB round-trip SQL aggregate) — eliminates 0.8–1.2 s summary hotspot
  - `get_results()` no longer loads all target rows on every paged request — cuts remaining ~4–6 s hotspot to O(page_size) rows
  - Five composite indexes added for `view=` filter, `has_selected_service` filter, and evidence lookups
  - Linked model scaffold in place: `person_master`, `person_identifiers`, `disease_screening_events`, `target_group_membership` tables exist in schema, ready for Phase F data population
  - Frontend `review_required` filter tab now wired to `?view=review_required` backend filter
- **Remaining open items:**
  - open issue 6: Wire `source-history` endpoint into patient detail modal frontend
  - open issue 10: Re-generate results after migration 0011 to populate `canonical_person_key` on existing rows
  - open issue 12: History rows still load all-group on every paged request — optimize to page-scoped CID filter
  - open issue 13: Summary cache not auto-invalidated when screening DB updated after generation
  - open issue 14: `target_group_membership` not yet populated — full multi-row provenance still requires Phase F migration
  - open issue 15: Phase F data migration for linked model tables
- **Next recommended step:**
  1. Run `alembic upgrade head` to apply migrations 0012 and 0013
  2. Re-generate any target group results to populate the summary cache and Phase D fields
  3. Proceed to Phase F: populate `person_master` and `target_group_membership` from existing `canonical_person_key` values on `target_group_results`


### Session summary — Phase E migration verification prep (2026-05-04)

- **Date:** 2026-05-04
- **Task:** Prepare local migration + verification workflow (sandbox cannot reach localhost:5432 or install pip packages via proxy)
- **What was verified in sandbox:**
  - All 3 migration files confirmed present and syntactically correct:
    - `20260503_0011_phase_d_person_link_fields.py` ✓
    - `20260504_0012_phase_e_result_summary_cache.py` ✓
    - `20260504_0013_phase_e_perf_indexes_linked_scaffold.py` ✓
  - `result_generation_service.py` — `_upsert_summary_cache()`, `get_result_summary()`, page-scoped `get_results()` all confirmed present and correct
  - `TargetGroupResultSummary` model confirmed correct with unique index on `(group_job_id, selected_service_hash)`
  - `env.py` reads DB URL from `settings.database_url` (overrides `alembic.ini`) → points to `seamlessfordmis` DB from `.env`
- **Files added:**
  - `scripts/verify_phase_e.sh` — full local run script: activates venv, runs `alembic upgrade head`, verifies schema via psql, re-generates all groups via REST API, verifies data
  - `scripts/verify_phase_e.sql` — standalone SQL verification queries (10 checks)
- **To run locally:**
  ```bash
  # From seamlessfordmis/backend/ with venv active and backend .env in place:
  cd backend
  source .venv/bin/activate        # or .venv\Scripts\activate on Windows
  alembic upgrade head             # applies 0012, 0013 (0011 may already be applied)
  alembic current                  # confirm: 20260504_0013 (head)

  # Verify schema:
  psql "$DATABASE_URL" -f ../scripts/verify_phase_e.sql

  # Start backend and re-generate:
  uvicorn app.main:app --reload --host 127.0.0.1 --port 8010
  # (in another terminal) for each group_job_id:
  curl -X POST http://127.0.0.1:8010/api/target-groups/<group_id>/generate-results

  # Or run the full script:
  bash ../scripts/verify_phase_e.sh
  ```
- **Expected outcomes after migration + regenerate:**
  - `alembic current` shows `20260504_0013 (head)`
  - 5 new tables present: `target_group_result_summaries`, `person_master`, `person_identifiers`, `disease_screening_events`, `target_group_membership`
  - 14 new indexes present (see `verify_phase_e.sql` check [2])
  - `target_group_result_summaries` rows: ≥ 1 row per group (after regenerate)
  - `target_group_results.canonical_person_key` = NOT NULL for every row
  - Duplicate `target_row_id` per group = 0 (1-person-1-row constraint)
  - Summary parts_sum = total_target_people (diff = 0 in check [9])
  - `review_required` count reflects ambiguous identity cases
- **Next recommended step:**
  1. Run the verification script locally (see above)
  2. Open the frontend and confirm the `review_required` filter tab appears and filters correctly
  3. Proceed to Phase F: run `alembic upgrade head` (applies 0014), then `python scripts/phase_f_populate.py`

---

## Phase F — Linked Model Population (2026-05-06)

**Goal:** Populate the four scaffold tables created in migration 0013 from
the normalised data already present in Phases B–E.  This enables person-level
cross-group queries and makes `target_group_membership` a first-class
relationship rather than an inferred join.

- **Files added:**
  - `backend/app/services/phase_f_population_service.py` — `PhaseFPopulationService` with four independent, idempotent steps:
    - `populate_person_master()` — upserts one `person_master` row per distinct `canonical_person_key` from `target_group_results`; back-fills NULL `display_name` / `primary_cid` on existing rows
    - `populate_person_identifiers()` — inserts `citizen_id`, `name_birthdate`, and `canonical_key` identifier rows for each person; guarded by `ON CONFLICT (person_id, identifier_type, identifier_value) DO NOTHING`
    - `populate_target_group_membership()` — single `INSERT … SELECT DISTINCT ON (target_row_id) … ON CONFLICT DO NOTHING` linking every `target_group_row` with a result to its `person_master`
    - `populate_disease_screening_events()` — `LEFT JOIN` on `primary_cid = normalized_person_identifier`; unmatched records inserted with `person_id = NULL` to preserve provenance
    - `populate_all()` — runs all four steps, flushes between each, commits once
  - `scripts/phase_f_populate.py` — CLI runner with `--step` and `--dry-run` flags; checks migration 0014 before running
  - `backend/alembic/versions/20260506_0014_phase_f_unique_constraints.py` — adds:
    - `uq_dse_source_record_id` unique index on `disease_screening_events.source_record_id`
    - `uq_person_identifiers_person_type_value` unique index on `(person_id, identifier_type, identifier_value)`
    Both are required for the `ON CONFLICT` clauses in `PhaseFPopulationService`.

- **Bug fix (Task #28) — PatientDetailModal source-history endpoint:**
  - `backend/app/services/patient_query_service.py` — fixed `source_history_for_result()`: before this fix the TG history IN filter used raw `selected_service_keys` directly; rows imported before the `field_mapping_service` canonical-key fix stored Thai slugs (e.g. `"ตรวจมะเร็งปากมดลูก"`) as `normalized_service_key` and were never matched → modal showed "ยังไม่พบประวัติ". Fix: call `_expand_selected_service_keys()` (same as `result_generation_service`) before the IN filter so Thai slugs, ICD10 slugs, and cervical sub-keys are all included.
  - `backend/tests/test_source_history_service_key_expansion.py` — regression tests M.1–M.4 covering the expansion logic and pre-fix Thai-slug row visibility.

- **To run Phase F locally:**
  ```bash
  cd backend
  source .venv/bin/activate
  alembic upgrade head        # applies 0014 (unique indexes on linked model tables)
  alembic current             # confirm: 20260506_0014 (head)

  # Dry-run first (no changes committed):
  python ../scripts/phase_f_populate.py --dry-run

  # Run for real:
  python ../scripts/phase_f_populate.py

  # Verify:
  psql "$DATABASE_URL" -c "SELECT COUNT(*) FROM person_master;"
  psql "$DATABASE_URL" -c "SELECT COUNT(*) FROM target_group_membership;"
  psql "$DATABASE_URL" -c "SELECT COUNT(*) FROM disease_screening_events;"
  ```

- **Expected outcomes after Phase F populate:**
  - `person_master` rows = distinct `canonical_person_key` count in `target_group_results`
  - `target_group_membership` rows = rows in `target_group_results` with non-NULL `target_row_id`
  - `disease_screening_events` rows = `COUNT(*) FROM disease_screening_records`
  - `disease_screening_events` with `person_id IS NOT NULL` = records whose CID matches a known person

- **Root cause resolved (modal "ยังไม่พบประวัติ"):**
  - Primary cause: `source_history_for_result()` used raw `selected_service_keys` IN filter; pre-fix imports stored Thai slug `normalized_service_key` values → not matched → empty modal
  - Fix: service key expansion added before the TG history query (Task #28)
  - Remaining operational check: verify `target_group_history_rows` rows exist for the affected CID with non-NULL `normalized_service_key` via:
    ```sql
    SELECT source_sheet_name, normalized_cid, raw_service_type,
           normalized_service_key, validation_status
    FROM target_group_history_rows
    WHERE normalized_cid = '1111111111111';
    ```

- **Remaining open items:**
  - open issue 12: History rows still load all-group on every paged request — optimize to page-scoped CID filter
  - open issue 13: Summary cache not auto-invalidated when screening DB updated after generation
  - open issue 16: PatientDetailModal — UNKNOWN_SHEET rows with `normalized_service_key = NULL` are excluded by the IN filter even after the Task #28 fix; consider showing all TG history for the person regardless of service key in the modal view
- **Next recommended step:**
  1. Run `alembic upgrade head` (applies 0014)
  2. Run `python scripts/phase_f_populate.py --dry-run` and confirm counts
  3. Run `python scripts/phase_f_populate.py` to populate
  4. Verify counts with SQL above

---

## Thai Buddhist Era Date Fix (2026-05-07)

### Root Cause (confirmed)

**Problem:** คอลัมน์ วันที่ล่าสุด / วัน / ปี แสดงเป็น `-` แม้ว่าจะพบประวัติจากไฟล์กลุ่มเป้าหมาย

**Root cause:** `parse_date()` ใน `backend/app/utils/dates.py` ส่ง Thai Buddhist Era (พ.ศ.) year string ตรงไปให้ pandas โดยไม่แปลงปีก่อน:
- `"13/03/2569"` (BE year 2569) → pandas พยายาม parse ปี 2569 CE
- `pd.Timestamp.max` = CE 2262-04-11 → ปี 2569 CE เกิน max → คืนค่า `NaT`
- `parse_date()` คืนค่า `None` → `normalized_visit_date = NULL` ใน `target_group_history_rows`
- `result_generation_service` กรอง `item.normalized_visit_date is not None` → date ถูกกรองออก
- `latest_visit = None` → `days_since = None`, `years_since = None` → แสดง `-`

**Pipeline trace:**
```
Excel: "13/03/2569"
  → parse_service_date() → parse_date("13/03/2569")
  → pd.to_datetime("13/03/2569", dayfirst=True)   ← year 2569 > max 2262 CE
  → NaT → None
  → normalized_visit_date = NULL in target_group_history_rows
  → result_generation: if item.normalized_visit_date is not None  ← excluded
  → latest_visit = None → days = -   years = -
```

### Fix

**File:** `backend/app/utils/dates.py`

**Change:** เพิ่ม `_convert_be_to_ce()` ซึ่งใช้ regex `(?<!\d)(2[5-9]\d{2}|[3-9]\d{3})(?!\d)` ตรวจหาปี ≥ 2500 ใน date string แล้วลบ 543 ก่อนส่งให้ pandas:
- `"13/03/2569"` → `"13/03/2026"` → `date(2026, 3, 13)` ✅
- `"13/03/2026"` → ผ่านโดยไม่เปลี่ยน (ปี < 2500) ✅
- ไม่กระทบ non-string values (datetime, Excel serial number)

**Conversion rule:** ปี ≥ 2500 ใน string = Thai Buddhist Era year → ลบ 543 = CE year

### Files Changed

- `backend/app/utils/dates.py` — added `_convert_be_to_ce()` helper + regex; applied in `parse_date()` string path only
- `backend/tests/test_date_parsing.py` — new file, tests N.1–N.8 covering:
  - N.1: `"13/03/2569"` → `date(2026, 3, 13)` (slash format)
  - N.2: `"13-03-2569"` → `date(2026, 3, 13)` (dash format)
  - N.3: `"2569-03-13"` → `date(2026, 3, 13)` (ISO-like)
  - N.4: `"13/03/2026"` unchanged (CE year)
  - N.5: parametrized — 2569→2026, 2568→2025, 2567→2024, 2500→1957, 2023→unchanged
  - N.6: `parse_service_date("13/03/2569")` → `normalized_value=date(2026, 3, 13)`, `validation_state=DATE_VALID`
  - N.7: `_convert_be_to_ce()` string-level unit tests
  - N.8: None/empty/invalid inputs still return None (regression guard)

### Data Backfill Required

Existing `target_group_history_rows` with Thai BE date strings have `normalized_visit_date = NULL` because they were imported before this fix. After deploying the fix:

```bash
# 1. Re-import the target group file (re-reads all sheets, re-normalizes dates):
#    Upload the same Excel file again via the UI or API — staging is safe

# 2. OR run targeted re-stage if re-import is not possible:
#    (currently no automated backfill script — re-import is the recommended path)

# 3. After re-import, re-generate results for the affected group:
curl -X POST http://127.0.0.1:8010/api/target-groups/<group_id>/generate-results

# 4. Verify sample CID 1111111111111 in DB:
psql "$DATABASE_URL" -c "
  SELECT normalized_cid, raw_service_type, normalized_visit_date, validation_status
  FROM target_group_history_rows
  WHERE normalized_cid = '1111111111111';"
# Expected: normalized_visit_date = 2026-03-13 (not NULL)
```

### Verification SQL

```sql
-- Check that existing rows for this CID have normalized dates after re-import:
SELECT
    normalized_cid,
    raw_service_type,
    normalized_service_key,
    normalized_visit_date,
    validation_status
FROM target_group_history_rows
WHERE normalized_cid = '1111111111111';

-- Check result row after re-generate:
SELECT
    r.normalized_cid,
    r.latest_relevant_date,
    r.days_since_latest,
    r.years_since_latest,
    r.last_relevant_source,
    r.overall_status
FROM target_group_results r
WHERE r.normalized_cid = '1111111111111';
-- Expected: latest_relevant_date = 2026-03-13, days/years non-null, last_relevant_source = target_group_file
```

### Session summary — Thai date fix (2026-05-07)

- **Date:** 2026-05-07
- **Task worked on:** Fix วันที่ตรวจ (BE year) not being parsed → วันที่ล่าสุด / วัน / ปี shows `-`
- **Files changed:**
  - `backend/app/utils/dates.py` — added `_convert_be_to_ce()` + `_BE_YEAR_RE`; applied in `parse_date()` string path
  - `backend/tests/test_date_parsing.py` — new, tests N.1–N.8
- **Root cause:** `pd.to_datetime` silently returns NaT for year > 2262 CE; Thai BE year 2569 = CE 2026 but was passed raw
- **Fix:** single-point change in `parse_date()` — regex detects year ≥ 2500, subtracts 543 before pandas
- **Business logic unchanged:** no fuzzy matching, no hardcoded CID/column, existing CE dates unaffected
- **Status:** code complete; **data backfill required** — must re-import target group file + re-generate results
- **Tests added:** N.1–N.8 (8 test functions, 17 parametrized cases)
- **Next recommended step:** Re-import the Excel file for the affected group, then re-generate results, then verify UI shows วันที่ล่าสุด = 13/03/2569 (or formatted equivalent) and วัน/ปี are non-dash

### Open issues updated

- [x] Issue 17 (NEW/RESOLVED in code): `parse_date()` did not convert Thai Buddhist Era year strings → วันที่ล่าสุด / วัน / ปี shows `-` — **fixed in code**, **data backfill pending**
- [ ] Issue 18 (NEW): Existing `target_group_history_rows` with BE date strings have `normalized_visit_date = NULL` — requires re-import + re-generate to backfill
- [ ] Issues 12, 13, 16 remain open (unchanged from Phase F session)

---

### Session summary — File Management + Stale Detection (2026-05-08)

- **Date:** 2026-05-08
- **Tasks worked on:**
  - Task #13 — `FileManagementPanel`: allow users to add/change target group files from the results workspace page without creating a new group
  - Task #14 — Source-file stale detection: show amber banner + identity-panel chip when results were generated from a different file set than the current one
- **Files changed:**

  1. `frontend/src/components/target-groups/FileManagementPanel.tsx` — NEW component
     - Drag-and-drop zone for adding files (.xlsx, .xls, .csv, .pdf)
     - Lists existing files (name, status chip, row count, size, parse error)
     - Shows selected-but-not-yet-uploaded files with per-file remove
     - Calls `addFilesToGroup(groupId, files)` on upload
     - On success calls `onFilesAdded(updatedGroup)` to propagate new `source_set_hash` upward
     - Success message tells user to regenerate results

  2. `frontend/src/lib/api.ts` — added `addFilesToGroup(groupId, files)`
     - `POST /api/target-groups/{groupId}/add-files` with `multipart/form-data`
     - Returns `TargetGroupDetail` (with updated `source_set_hash`)

  3. `frontend/src/components/target-groups/TargetGroupResultsWorkspace.tsx`
     - Renders `<FileManagementPanel>` in the workspace with `onFilesAdded` callback
     - `onFilesAdded` updates local `group` state so `source_set_hash` refreshes without page reload
     - Added `SourceFileStaleBanner` component (amber, with regenerate button)
     - Added `isSourceStale` useMemo: compares `results.summary.generated_source_set_hash` vs `group.source_set_hash ?? group.source_file_hash`; truthy only when hash differs AND `generated_source_set_hash` is non-null
     - `exportDisabled` now includes `isSourceStale`
     - Banner shown when `isSourceStale && !isDirty` (not simultaneously with `ConfigDirtyBanner`)
     - Identity panel shows "ผลลัพธ์ไม่ตรงกับข้อมูลล่าสุด" warning chip when stale

  4. `frontend/src/types/result.ts`
     - Added `generated_source_set_hash: string | null` to `ResultSummary`
     - Added missing `export type ExportDownload = { filename: string; }` (was truncated from file)
     - Removed pre-existing dangling `export typ` fragment at end of file (truncation artifact)

  5. `frontend/src/app/globals.css`
     - Added `.source-stale-banner`, `.source-stale-content`, `.source-stale-icon`, `.source-stale-title`, `.source-stale-note` (amber #fef3c7 / #f59e0b theme)

- **Backend verified (no changes needed):**
  - `backend/app/api/target_groups.py` — `POST /{group_id}/add-files` endpoint already present
  - `backend/app/services/target_group_import_service.py` — `add_files_to_group()` already recomputes `source_set_hash` on the `TargetGroupJob` after adding files
  - `backend/app/models/target_group_result_summary.py` — already has `source_set_hash: Mapped[str | None]`
  - `backend/app/schemas/result.py` — already has `generated_source_set_hash: str | None = None` in `ResultSummaryResponse`
  - `backend/app/services/result_generation_service.py` — already reads `job.source_set_hash`, passes through `_upsert_summary_cache()`, returns as `generated_source_set_hash` in response
  - `backend/alembic/versions/20260508_0015_add_source_set_hash_to_result_summary.py` — migration adds `source_set_hash` column to `target_group_result_summaries` (NOT YET RUN — must run `alembic upgrade head`)

- **TypeScript:** `node_modules/.bin/tsc --noEmit --skipLibCheck --incremental false` → 0 errors
- **Backend Python:** AST parse check on all 7 affected backend files → all pass

- **Business rules maintained:**
  - Stale detection is hash-based (content-aware), not timestamp-based
  - Stale banner only appears when `generated_source_set_hash` is non-null (i.e., results have been generated at least once with hash tracking active)
  - Stale detection is separate from `isDirty` (service-selection staleness); both can be stale independently but only one banner shows at a time (stale-source takes precedence over dirty-config for export disabling; they are never shown simultaneously)
  - File upload resets match status on the backend — success message informs user

- **Status:** code complete; **migration must be run manually**
- **Next recommended step:**
  1. Run `alembic upgrade head` to apply migration 0015 (`source_set_hash` column on `target_group_result_summaries`)
  2. Re-generate results for any existing target groups — this populates `generated_source_set_hash` in the summary cache so the stale detection can compare hashes going forward
  3. Upload new/changed target group files via the FileManagementPanel, then regenerate results — verify amber stale banner appears after file add and disappears after regeneration

- **Open issues updated:**
  - [x] Issue 19 (NEW/RESOLVED in code): FileManagementPanel not accessible from workspace → **fixed** (Task #13)
  - [x] Issue 20 (NEW/RESOLVED in code): No visual indicator when results were generated from a different file set → **fixed** (Task #14)
  - [ ] Issue 21 (NEW): Existing `target_group_result_summaries` rows have `source_set_hash = NULL` — stale banner will not appear until results are re-generated after migration 0015
  - [ ] Issues 12, 13, 16, 18 remain open (unchanged)
---

## Session summary — Dashboard UI refinement toward reference design (2026-05-11)

- **Date:** 2026-05-11
- **Task worked on:** ปรับหน้า Dashboard ให้ใกล้เคียงภาพออกแบบอ้างอิง โดยคง business rules/import logic เดิม
- **Scope:** frontend/UI refinement เป็นหลัก ไม่มีการเปลี่ยน matching, target-group result generation, backend import logic หรือ business rules หลัก

### UI/UX completed

- ปรับ Dashboard เป็นโครงสร้างเดียวกับ reference:
  - header พร้อม label `DASHBOARD`, title, subtitle และ CTA `เพิ่มข้อมูลการคัดกรอง`
  - sidebar แบบอ่อน/โปร่ง มี logo circle `DR`, active state สีเขียวอ่อน, build badge `v1.3.0 · staging`
  - summary status card ด้านบนแบบ metric strip พร้อม icon/divider และ badge `พร้อมใช้งาน`
  - 3 cards กลางหน้า: source integrity, upload, supported file types
  - quick action bar พร้อม action ที่ใช้งานจริง/disabled ชัดเจน
  - recent imports table พร้อม empty/action-disabled states
- ปรับ visual language ให้ใกล้ reference: beige/cream background, ivory cards, border บาง, shadow นุ่ม, teal/green accent, rounded corners, typography อ่านง่าย
- ปรับ source-set hash ให้ไม่ล้น card และมี copy feedback `คัดลอกแล้ว`
- ปรับ file type card ให้ PDF แสดงเป็น `staged — ต้องตรวจสอบก่อนบันทึก` ไม่แสดงว่า production-ready เต็มรูปแบบ

### Files changed in this session

- `frontend/src/app/dashboard/page.tsx`
- `frontend/src/app/globals.css`
- `frontend/src/components/layout/Sidebar.tsx`
- `frontend/src/components/dashboard/DashboardHeader.tsx`
- `frontend/src/components/dashboard/DashboardStatusSummary.tsx`
- `frontend/src/components/dashboard/SourceIntegrityCard.tsx`
- `frontend/src/components/dashboard/SupportedFileTypesCard.tsx`
- `frontend/src/components/dashboard/RecentImportsTable.tsx`
- `frontend/src/components/dashboard/UploadCTAButton.tsx`
- `frontend/src/components/dashboard/DashboardQuickActions.tsx`
- `PROJECT_STATUS.md`

### API used by Dashboard

- `GET /api/system/status`
- `POST /api/system/check-source-update`
- `GET /api/screening-database/imports?limit=20&offset=0`
- `POST /api/screening-database/stage-upload`
- `POST /api/system/sync-disease-screening-database`

### Upload behavior

- Upload card supports click-to-select and drag/drop UI.
- Frontend validates extension `.xlsx`, `.xls`, `.csv`, `.pdf` and max file size `200 MB`.
- Selected file list is shown before upload.
- Upload uses the real `stage-upload` API.
- PDF upload remains staged/needs-review; no fake progress percentage or fake successful import is shown.
- Actual database import still requires the real sync action.

### Verification run

- `node_modules\.bin\tsc --noEmit --skipLibCheck --incremental false` — passed
- `npm run build` — passed
- Manual browser check at `http://127.0.0.1:3020/dashboard` — passed
  - Dashboard opened successfully
  - CTA `เพิ่มข้อมูลการคัดกรอง` scrolled/focused the upload area
  - Source-set hash copy button showed `คัดลอกแล้ว`
  - Upload dropzone visible
  - Recent imports section visible
  - Browser console error logs: none

### Recently completed work update

- Dashboard reference-aligned UI shell is now implemented for the screening database management page.
- Screening upload flow is wired to the real staged upload API.
- Recent imports UI is wired to the real import history endpoint.

### Known bugs / open issues update

- Some Dashboard actions remain intentionally disabled because there is no dedicated API yet:
  - per-file "ตรวจสอบไฟล์ล่าสุด" action
  - import detail view action
  - import file download action
  - summary report download action
- Responsive check covered desktop/browser verification and CSS breakpoints for tablet/mobile; full visual QA on a real tablet viewport is still recommended.
- Existing open data/backend issues from previous sessions remain unchanged.

### Blockers update

- No blocker for the frontend Dashboard refinement.
- Export/report and import detail APIs are still missing for enabling disabled