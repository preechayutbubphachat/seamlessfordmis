# Desktop Shell Prototype (D3 — Minimal)

Last updated: 2026-06-11 (D4 session)
Status: **Prototype** — ไม่ใช่ production installer / EXE — ยังไม่ผ่าน Windows clean-machine test

## 1. Current launcher status

- `backend/app/desktop/launch.py` — force `desktop_local` + SQLite ก่อน import settings, bind `127.0.0.1` เท่านั้น
- Sandbox (Linux) validation ผ่าน: `/health` ok, listener เป็น `127.0.0.1:8010` เท่านั้น (ตรวจด้วย `ss -tlnp`)
- **Windows validation: PASSED (2026-06-11)** — D4 ต่อไป: เปิดหน้าแอปจริงผ่าน static bundle (`npm run desktop:build` แล้ว launcher จะเปิด `http://127.0.0.1:8010/` อัตโนมัติ) — ใช้ `backend\scripts\check_desktop_launcher.bat` (wrapper) → `check_desktop_launcher.ps1` (logic จริง, อัตโนมัติทั้งหมด รวม start/stop launcher)
  - v1 (.bat ล้วน) พังเพราะ batch parser — แก้เป็น PowerShell แล้ว (2026-06-11) ห้ามย้าย logic กลับไป .bat
- D3.2: launcher เลือกหน้าเปิดอัตโนมัติ — ถ้า frontend รันอยู่ที่ `127.0.0.1:3020` จะเปิดหน้า app, ไม่งั้นเปิด `/docs` (override ได้ด้วย `DESKTOP_OPEN_URL`, รับเฉพาะ loopback URL)

## 2. How to run on Windows

```bat
cd C:\2025\web-69\โรงบาลหนองพอก\seamlessfordmis\backend
.venv\Scripts\activate
python -m app.desktop.launch
```

หรือรันชุดตรวจ 10 ข้อ: `backend\scripts\check_desktop_launcher.bat` แล้ว copy ผลกลับมารายงาน

## 3. Expected /health result

```json
{"status":"ok","app_edition":"desktop_local","database_engine":"sqlite"}
```

## 4. Data folder behavior

| Path | ใช้ทำอะไร |
|---|---|
| `data/seamlessfordmis.db` | SQLite DB — สร้างอัตโนมัติถ้ายังไม่มี, **ไม่ overwrite ของเดิม** |
| `data/exports/`, `data/backups/` | export/backup (gitignored สำหรับไฟล์ใหม่) |
| `uploads/target_groups/` | ไฟล์ upload |
| `logs/` | log dir (access log ปิด — กัน identifier ลง log) |
| `backend/config/settings.json` | desktop settings snapshot (gitignored) |

DB อยู่ใน repo data dir ระหว่าง prototype — **ก่อนทำ installer ต้องย้ายไป `%LOCALAPPDATA%`** กัน uninstaller ลบข้อมูล (บันทึกเป็น D4+ requirement แล้ว)

## 5. SQLite behavior

- Engine บังคับผ่าน env `DATABASE_ENGINE=sqlite` + `DATABASE_URL` ชี้ `data/seamlessfordmis.db`
- Schema init ตอน startup (`create_all` — additive, ไม่ destructive)
- หมายเหตุ dev: บน Cowork sandbox mounted FS จะเจอ `disk I/O error` — ต้องชี้ DB ไป `/tmp` (เฉพาะ sandbox, ไม่เกิดบน Windows local disk)

## 6. Port binding rule

- **127.0.0.1 เท่านั้น** — ห้าม 0.0.0.0 / LAN IP
- Default port 8010, เปลี่ยนด้วย `DESKTOP_PORT`
- `DESKTOP_OPEN_URL` รับเฉพาะ `http://127.0.0.1...` / `http://localhost...`

## 7-8. Known limitations

- ยังไม่ใช่ EXE/installer — ต้องมี Python venv
- **Frontend integration = Option B (D4, implemented):** `npm run desktop:build` สร้าง `frontend/out` → FastAPI serve ที่ `/` (desktop_local เท่านั้น) → ผู้ใช้ปลายทางไม่ต้องมี Node.js
- หน้า detail ใช้ query param (`/patients/detail?id=`, `/target-groups/detail?id=`) แทน `[id]` routes (ลบแล้ว — UUID runtime export ไม่ได้)
- Static bundle ยังไม่ถูก build/validate บน Windows (sandbox build ติด mnt FS SIGBUS)
- `NEXT_PUBLIC_API_BASE_URL` เป็น build-time constant → ถ้าจะใช้ dynamic port ในอนาคต ต้องมี runtime config injection (เช่น backend serve `/desktop-config.json`) — แผนไว้ใน D4
- ไม่มี single-instance lock (เปิดซ้ำ = ตัวที่สองแจ้ง port ชนแล้วจบ — ปลอดภัยแต่ยังไม่ user-friendly)
- ยังไม่มี backup-on-start / legacy DB migration guard

## 9. Troubleshooting

| อาการ | วิธีแก้ |
|---|---|
| Port occupied | launcher แจ้ง error + วิธีตั้ง `DESKTOP_PORT` — ตรวจว่ามี instance เก่าค้าง: `netstat -ano \| findstr :8010` แล้ว `taskkill /PID <pid>` |
| Dependency missing | `pip install -r requirements.txt` ใน venv; ตรวจ `python -m compileall app -q` |
| SQLite path error | ตรวจสิทธิ์เขียนใน `data/`; path ไทยใช้ได้ (launcher ใช้ `Path.as_posix()`); ถ้า disk I/O error ตรวจ filesystem |
| Browser ไม่เปิด | เปิดเอง: `http://127.0.0.1:8010/docs` — ตัว backend ไม่เกี่ยวกับ browser |
| เปิดได้แต่เป็น /docs ไม่ใช่หน้า app | ยังไม่มี static bundle — `cd frontend && npm run desktop:build` แล้วรัน launcher ใหม่ (หรือรัน dev server) |

## 10. Next phase

1. ✅ Windows launcher validation PASSED (2026-06-11)
2. ✅ Frontend static bundle implemented (D4) — เหลือ build + validate บน Windows: `npm run desktop:build`
3. Workflow validation 13 ข้อ: `docs/DESKTOP_D4_WORKFLOW_VALIDATION.md` (synthetic fixtures เท่านั้น)
4. Runtime config injection สำหรับ API base (dynamic port) — D5
5. Single-instance lock + ย้าย data dir ไป `%LOCALAPPDATA%` — D5 ก่อน installer
6. Data privacy: ตัดสินใจ `git rm --cached data/` ตาม `docs/DATA_PRIVACY_GIT_TRACKING_AUDIT.md`
