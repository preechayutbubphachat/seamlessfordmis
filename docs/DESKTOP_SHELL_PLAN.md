# Desktop Shell — Implementation Plan (Phase D3, pre-gate)

> **สถานะ:** PLAN เท่านั้น — ยังไม่เริ่มเขียน shell code
> **เงื่อนไขเริ่ม implement:** D3 gate ต้องผ่านก่อน (G1 `pytest tests/test_desktop_sqlite_workflow.py` เขียว + G5 ไม่ regression บนเครื่องจริง)
> **วันที่:** 2026-05-30

เอกสารนี้คือพิมพ์เขียวพร้อม implement สำหรับ Desktop Local Shell เพื่อให้ลงมือได้ทันทีหลัง gate เขียว โดยไม่แตะ business logic และไม่กระทบ Docker/LAN edition

---

## 1. ขอบเขต / ไม่ใช่ขอบเขต

**ใช่:** เปิดโปรแกรมเดียวบนเครื่องผู้ใช้ → สตาร์ท FastAPI backend (SQLite) บน `127.0.0.1` → เปิดหน้า UI → ปิดแล้ว stop backend
**ไม่ใช่ (รอบนี้):** production installer, auto-update, code signing, backup/restore UI, system tray ครบ — เป็น D4/D5

**ไม่แตะ:**
- `launcher/seamlessfordmis_launcher.py` (อันนี้คือ launcher ของ **Docker/LAN edition** — แยกกันคนละตัว ห้ามลบ/แก้)
- matching / result generation / import-mapping / provenance / audit (business logic)

---

## 2. สิ่งที่มีอยู่แล้ว (re-use ได้ทันที)

| มีอยู่ | ใช้ทำอะไรใน D3 |
|---|---|
| `backend/app/desktop/paths.py` → `init_desktop_paths()` | สร้าง local data folder + คืน path (db = `data_dir/seamlessfordmis.db`) |
| `backend/app/desktop/init_db.py` → `init_desktop_db()` | bootstrap schema SQLite (บังคับ `APP_EDITION=desktop_local`+`DATABASE_ENGINE=sqlite`) |
| `backend/app/main.py` | FastAPI app — สตาร์ทด้วย uvicorn ได้เลย |
| `.env.example` / config `is_desktop_local` / `is_sqlite` | สลับ edition ด้วย env |

D3 จึงเป็นแค่ "glue" + การ serve frontend แบบ offline ไม่ใช่ของใหม่ทั้งก้อน

---

## 3. การตัดสินใจสถาปัตยกรรม (ต้องเคาะก่อนลงมือ)

### 3.1 จะ serve frontend ยังไงโดยไม่ต้องมี Node บนเครื่องปลายทาง
ข้อจำกัด: ผู้ใช้ปลายทาง **ห้ามต้องลง Node.js** → รัน `next start` บนเครื่องปลายทางไม่ได้

**ผลตรวจจริงของ frontend (2026-05-30, evidence-based):**
- Next.js `15.2.4`, App Router, **ไม่มี API route ฝั่ง server เลย** (ไม่มี `app/api`, `route.ts`, `pages/api`) → ดีต่อ offline
- `next.config.js` ปัจจุบัน **ไม่ได้** ตั้ง `output: "export"` (มีแค่ `distDir`)
- `src/lib/api.ts`: `API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8010"` → fetch ฝั่ง client ได้, ตั้ง same-origin ได้ด้วย `NEXT_PUBLIC_API_BASE_URL=""`
- **อุปสรรคจริงต่อ static export:** 4 หน้าเป็น **async Server Component** ที่ `await` เรียก API ฝั่ง server ตอน request และตั้ง `export const dynamic = "force-dynamic"`:
  - `app/dashboard/page.tsx`, `app/target-groups/page.tsx`
  - `app/patients/[id]/page.tsx`, `app/target-groups/[id]/page.tsx` (dynamic route `[id]` ไม่มี `generateStaticParams`)
  → `output: "export"` แบบ drop-in **ใช้ไม่ได้** ต้องแก้ frontend ก่อน

**ทางแยกที่ต้องเคาะ (เป็น infra ไม่ใช่ business logic — แต่ต้องอนุมัติ):**

| ตัวเลือก | สิ่งที่ต้องทำ | ข้อดี | ข้อเสีย |
|---|---|---|---|
| **A. Refactor → static export** (แนะนำระยะยาว) | แปลง 4 หน้า SSR เป็น client component ที่ fetch ผ่าน `/api` ฝั่ง client, เอา `force-dynamic` ออก, ใส่ `generateStaticParams`/ทำ `[id]` แบบ client-only, ตั้ง `output:"export"` + `NEXT_PUBLIC_API_BASE_URL=""` แล้วให้ FastAPI `StaticFiles` serve | ไม่มี Node runtime จริง, process เดียว, offline สุด | ต้องแก้ frontend 4 หน้า + ทดสอบว่า "ข้อมูลที่แสดง" ไม่เปลี่ยน (1คน=1แถว, provenance) |
| **B. Bundle portable Node + `next start`** | แพ็ค Node runtime เข้าชุดติดตั้ง รัน `next start` เป็น subprocess คู่กับ uvicorn | ไม่ต้องแตะ frontend เลย | ชุดใหญ่ขึ้น, 2 process, ผู้ใช้ไม่ต้องลง Node เองแต่ Node ถูก bundle |

**คำแนะนำ:** เริ่ม D3 prototype ด้วย **ตัวเลือก B ชั่วคราว** เพื่อ verify workflow ให้จบก่อน (ไม่แตะ frontend, เสี่ยงต่ำสุดต่อ business correctness) แล้วค่อยย้ายไป **A** ตอนทำ packaging จริง (D4/D5) เพื่อตัด Node ออก — การตัดสินนี้รอผู้ใช้ยืนยัน

### 3.2 หน้าต่าง UI
- **เริ่มจาก default browser** (`webbrowser.open`) — เบาสุด, dependency เป็นศูนย์, ใช้ verify workflow ได้ก่อน
- **pywebview** เป็น optional ขั้นถัดไป (embedded window) — เพิ่มเมื่อ flow ผ่านแล้ว
- **ไม่ใช้** Electron/Tauri/.NET รอบนี้ (scope บานปลาย)

---

## 4. ไฟล์ที่จะสร้าง (หลัง gate ผ่านเท่านั้น)

```
backend/app/desktop/launch.py        # entrypoint: python -m app.desktop.launch
docs/DESKTOP_SHELL_PROTOTYPE.md      # คู่มือรัน + limitations (สร้างเมื่อเริ่ม D3)
```
(อาจมี `backend/app/desktop/serve_frontend.py` ถ้าแยก StaticFiles mount ออกมา)

**ไม่สร้าง:** installer, .exe, spec ใหม่ — เป็น D4+

---

## 5. ลำดับการทำงานของ `app.desktop.launch` (pseudocode)

```text
1. ตั้ง/ยืนยัน env: APP_EDITION=desktop_local, DATABASE_ENGINE=sqlite
   - ถ้าไม่ใช่ desktop_local+sqlite → ออกพร้อม error ชัดเจน (กันสตาร์ทผิด edition)
2. init_desktop_paths()      # สร้าง data folder ทั้งหมด
3. init_desktop_db()         # create_all schema ถ้ายังไม่มี (idempotent)
4. หา free port; ถ้า 127.0.0.1:<port> ไม่ว่าง → เลือก port ถัดไป / แจ้งผู้ใช้ (graceful)
5. start uvicorn app.main:app  host=127.0.0.1  port=<port>  (ใน thread/subprocess)
6. รอ /api/system/status ตอบ 200 (health poll, timeout) ก่อนเปิด UI
7. print + แสดง: local URL, data folder, logs path
8. webbrowser.open(local URL)   # (pywebview ภายหลัง)
9. รอจน Ctrl+C / ปิดหน้าต่าง → shutdown uvicorn ให้เรียบร้อย
```

---

## 6. Safety checklist (บังคับ)

- [ ] bind `127.0.0.1` เท่านั้น — ห้าม `0.0.0.0` (กันเข้าถึงจาก LAN)
- [ ] ไม่มี telemetry / ไม่ auto-upload logs
- [ ] logs ห้ามมีข้อมูลผู้ป่วย / CID เต็ม
- [ ] port ไม่ว่าง → จัดการแบบ graceful ไม่ crash
- [ ] ไม่มี destructive action (ไม่ลบ DB/ไฟล์อัตโนมัติ)
- [ ] ไม่ commit DB/exports/backups/uploads จริงลง repo (`.gitignore` ต้องครอบคลุม)
- [ ] Docker/LAN edition ยังสตาร์ทได้เหมือนเดิม (ทดสอบว่าไม่ regression)
- [ ] ไม่ claim production-ready จนกว่าจะผ่าน clean machine test (D4+)

---

## 7. Task breakdown (เริ่มเมื่อ gate เขียว)

1. ยืนยัน 3.1 (frontend static export) กับเจ้าของโปรเจกต์
2. เพิ่ม StaticFiles mount ใน `app.main` แบบมี guard (เฉพาะเมื่อ desktop_local และมีโฟลเดอร์ static) — ไม่กระทบ LAN
3. เขียน `app/desktop/launch.py` ตามลำดับข้อ 5
4. ทดสอบ D2.19 real-world smoke (non-sensitive sample) ตาม flow ใน task เดิม
5. เขียน `docs/DESKTOP_SHELL_PROTOTYPE.md` (วิธีรัน, dependency, data folder, binding, limitations, why not production-ready)
6. อัปเดต `PROJECT_STATUS.md` + `project_architecture.md` (decision 3.1)

---

## 8. Acceptance ของ D3 minimal

- `python -m app.desktop.launch` เปิด backend SQLite + UI ได้บนเครื่อง dev โดยไม่ใช้ Docker/Node/Postgres
- ทำ workflow ครบ: import screening sample → import target group multi-sheet → generate → ดูตาราง (1 คน = 1 แถว) → export Excel → restart → ข้อมูลคงอยู่
- LAN/Docker edition ไม่ regression
- ไม่มี business logic เปลี่ยน
- docs + PROJECT_STATUS อัปเดต

> ยังเป็น prototype — ไม่ใช่ production. Production ต้องผ่าน clean machine test จริง (D4/D5)
