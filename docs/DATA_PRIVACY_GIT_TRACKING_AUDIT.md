# Data Privacy Git Tracking Audit

Date: 2026-06-11 (D3.2), reconfirmed 2026-06-16 (D4 code commit)
Status: **AUDIT ONLY — ยังไม่ได้ untrack ไฟล์ใด รอการอนุมัติจากเจ้าของ repo**

> 2026-06-16: ตรวจซ้ำ `git ls-files data | wc -l` = **70 ไฟล์ ยังเท่าเดิม** (54 .xlsx, 6 .XLS, 5 .xlsx ชื่อไทย, 2 .csv, 1 .txt, 1 .md). 3 ไฟล์ใน data/ เป็น modified แต่ **ไม่ถูก stage** ใน D4 code commit. การ commit โค้ด D3/D4/CID/SQLite/upload fix ทำแยกจาก data cleanup โดยสิ้นเชิง (stage เฉพาะ path โค้ด/test/docs — ดู PROJECT_STATUS session 9). `.gitignore` เพิ่มการกัน build artifact (`frontend/out/`, `*.exe`, `*.patch`, `tsconfig.tsbuildinfo`) แล้ว. **git rm --cached ข้อ 3 ยังไม่รัน — รออนุมัติ**

## 1. สรุปไฟล์ใน `data/` ที่ถูก git track

`git ls-files data` = **70 ไฟล์** แยกตามกลุ่ม:

| กลุ่ม | จำนวน | ตัวอย่าง | ความเสี่ยง |
|---|---|---|---|
| Source หลัก `11068_DKTP*.xlsx` | 41 | `11068_DKTP66111500001.xlsx` | **สูงมาก** — รหัสหน่วยบริการ 11068 + รูปแบบไฟล์ DKTP บ่งชี้ว่าเป็นไฟล์ฐานประวัติการตรวจจริงจากระบบโรงพยาบาล |
| Target group ราก `data/` | 6 | `มะเร็งปาก-64-1.xlsx`, `data/targets/หญิงไทยอายุ 30-60 ปี...XLS` | **สูงมาก** — ไฟล์กลุ่มเป้าหมายจริง น่าจะมี CID/ชื่อผู้ป่วย |
| `data/uploads/` | 10 | `1265e3eb-...xlsx` (UUID = อัปโหลดผ่านระบบจริง) | **สูงมาก** |
| `data/exports/` | 9 | `target-group-Phase-3-Smoke-Test-*.csv/xlsx`, `smoke-report.*` | **สูง** — บางไฟล์เป็น smoke test แต่ต้องเปิดตรวจทีละไฟล์ก่อนสรุปว่า synthetic |
| `data/samples/` | 3 | `live_target_group.xlsx` (ชื่อบอกว่า live!), `sample_target_group.xlsx`, README.txt | **ปนกัน** — `live_*` เสี่ยงสูง, `sample_*` ต้องเปิดตรวจ |
| `data/README.md` | 1 | คำอธิบาย directory | ไม่เสี่ยง — **ควร track ต่อ** |

## 2. สิ่งที่ควร track ต่อ (ห้าม ignore)

- `data/README.md`
- `backend/tests/fixtures/desktop_local/` — **synthetic fixtures ที่ test ต้องใช้** (CID สังเคราะห์ผ่าน DOPA check digit เท่านั้น) — .gitignore ปัจจุบันไม่แตะ path นี้ ✓
- `.env.example` / `frontend/.env.example`

## 3. คำสั่งที่แนะนำ (ห้ามรันจนกว่าจะอนุมัติ)

`git rm --cached` = เอาออกจาก git tracking เท่านั้น **ไฟล์จริงในเครื่องยังอยู่ครบ ไม่มีอะไรถูกลบ**

```bash
# untrack ทุกอย่างใน data/ ยกเว้น README (ไฟล์จริงไม่หาย):
git rm -r --cached data/
git add data/README.md
git commit -m "chore: untrack operational data files (privacy) - files remain on disk"
```

ข้อควรรู้สำคัญ:

1. หลัง untrack แล้ว `.gitignore` (อัปเดตแล้ว) จะกันไม่ให้ไฟล์กลับเข้ามาใหม่
2. **ไฟล์ที่เคย commit/push ไปแล้วยังอยู่ใน git history** — ถ้า repo นี้เคย push ไป remote ที่คนอื่นเข้าถึงได้ ต้องพิจารณา history cleanup (`git filter-repo`) แยกต่างหาก **ห้ามทำ history rewrite โดยไม่วางแผน backup และแจ้งทุกคนที่ clone repo**
3. ถ้า repo เป็น local-only บนเครื่องเดียว ความเสี่ยงการรั่วไหลต่ำกว่า — untrack + ignore เพียงพอสำหรับตอนนี้
4. ห้ามลบไฟล์จริงใน `data/` — ระบบ LAN edition ใช้ sync จากโฟลเดอร์นี้

## 4. .gitignore coverage (อัปเดต D3.2/D4)

ครอบคลุมแล้ว: `data/*.db`, `data/**/*.db`, `data/*.sqlite`, `data/**/*.sqlite`, `*.db-wal`, `*.db-shm`, `data/uploads/`, `data/source_files/`, `data/reports/`, `data/exports/`, `data/backups/`, `data/targets/`, `data/samples/`, `data/*.xlsx`, `data/*.XLS`, `logs/`, `.env`, `.env.*` (ยกเว้น `!.env.example`)

หมายเหตุ: .gitignore มีผลเฉพาะไฟล์ใหม่ — ไฟล์ 70 ตัวที่ track อยู่แล้วต้องใช้ `git rm --cached` ตามข้อ 3

## 5. Decision needed (เจ้าของ repo)

- [ ] อนุมัติ untrack `data/` ตามข้อ 3 หรือไม่
- [ ] repo เคย push ไป remote หรือไม่ → ถ้าใช่ ต้องวางแผน history cleanup
- [ ] เปิดตรวจ `data/exports/smoke-*` + `data/samples/sample_*` ว่า synthetic จริงไหม ถ้าใช่จะย้ายไป `tests/fixtures/` แล้ว track ต่อได้
