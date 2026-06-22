# คู่มือติดตั้งแบบ Offline/LAN สำหรับ seamlessfordmis

เอกสารนี้สำหรับ IT หน่วยงานที่ต้องการติดตั้งระบบ `seamlessfordmis` บนเครื่องแม่ข่ายภายใน โดยใช้ Docker Compose และเปิดใช้งานผ่าน LAN โดยไม่ต้องพึ่ง Shared Hosting, SSH, หรือ Python environment จาก hosting ภายนอก

## เหมาะกับใคร / ใช้งานในสถานการณ์ไหน

| สถานการณ์ | เหมาะสม? |
|-----------|----------|
| โรงพยาบาลชุมชน / สสอ. ไม่มี server กลาง ต้องการรัน local | ✅ เหมาะมาก |
| ต้องการให้หลายเครื่องใน LAN เดียวกันเข้าระบบพร้อมกัน | ✅ เหมาะมาก |
| ห้องปฏิบัติการ offline ที่ไม่มี internet | ✅ เหมาะมาก — ใช้ offline image export/load |
| ต้องการให้ข้อมูลผู้ป่วยไม่ออกนอกเครือข่ายหน่วยงาน | ✅ เหมาะมาก — ไม่มี call ออก internet |
| ต้องการ cloud backup หรือ multi-site sync | ❌ ไม่รองรับในแพ็กเกจนี้ |
| ต้องการ HTTPS / SSL certificate สาธารณะ | ❌ ต้องการการตั้งค่าเพิ่มเติม |

ระบบนี้ออกแบบมาให้ทำงานได้บน **เครือข่ายปิด** โดยเฉพาะ ข้อมูลทั้งหมดถูกประมวลผลและเก็บภายในเครื่องแม่ข่ายเท่านั้น

---

## ภาพรวมระบบ

ชุด offline package มี 4 service หลัก:

- `db` - PostgreSQL 16 เก็บข้อมูลระบบ
- `backend` - FastAPI รันที่พอร์ตภายใน `8010`
- `frontend` - Next.js production server รันที่พอร์ตภายใน `3000`
- `nginx` - reverse proxy เปิดให้ผู้ใช้เข้าเว็บผ่านพอร์ต `80`

เส้นทางใช้งาน:

- หน้าเว็บ: `http://localhost` หรือ `http://<IP เครื่องแม่ข่าย>`
- API ผ่าน nginx: `/api/...`
- Health check: `http://localhost/health`

## Requirement เครื่อง

- Windows 10/11 หรือ Linux
- Docker Desktop สำหรับ Windows หรือ Docker Engine สำหรับ Linux
- RAM ขั้นต่ำ 4 GB, แนะนำ 8 GB ขึ้นไป
- Disk space ขั้นต่ำ 20 GB, แนะนำ 50 GB ขึ้นไปถ้ามีไฟล์ Excel/PDF และ backup จำนวนมาก
- เครื่องแม่ข่ายควรตั้งรหัสผ่านและอยู่ในเครือข่ายที่ควบคุมได้

## ติดตั้งครั้งแรกบน Windows

1. ติดตั้งและเปิด Docker Desktop
2. แตกไฟล์หรือ clone project ลงเครื่องแม่ข่าย
3. เปิด Command Prompt หรือ PowerShell ที่ root ของ project
4. รัน:

```bat
offline\install.bat
```

script จะทำงานดังนี้:

- ตรวจว่า Docker ใช้งานได้
- copy `.env.offline.example` เป็น `.env` ถ้ายังไม่มี
- build image
- start PostgreSQL
- รอ database healthy
- รัน migration ด้วย `alembic upgrade head`
- start ทุก service

หลัง install ครั้งแรก ให้เปิด `.env` และเปลี่ยน `POSTGRES_PASSWORD` ก่อนใช้งานจริง

## GUI Launcher (วิธีที่ง่ายที่สุดสำหรับ Windows)

หากติดตั้งผ่าน Installer และมี GUI Launcher พร้อมใช้งาน ให้ดับเบิลคลิก shortcut **SeamlessFordMIS** บน Desktop
หรือเปิดโดยตรง:

```
C:\SeamlessFordMIS\app\SeamlessFordMIS-Launcher.exe
```

GUI Launcher มีฟีเจอร์:
- แสดงสถานะ Docker / ฐานข้อมูล / Backend / Frontend / nginx แบบ real-time (สีเขียว/เหลือง/แดง)
- ปุ่ม Start / Stop / Restart / เปิดเว็บ / Status / Logs / Backup / Restore / Migration / Load Images / LAN IP / Health Check
- Log output panel — ไม่แสดง password ใดๆ
- ต้องการ Docker Desktop รัน และ working directory ที่ถูกต้อง (`C:\SeamlessFordMIS\app\`)

> **หมายเหตุ:** GUI Launcher เป็น optional component — ถ้าไม่มี EXE ให้ใช้ `control-panel.bat` แทนได้

---

## แผงควบคุม Command Prompt (fallback)

สำหรับผู้ดูแลระบบที่ต้องการเมนูภาษาไทยพร้อมใช้งานใน Command Prompt ให้รัน:

```bat
offline\control-panel.bat
```

แผงควบคุมจะตรวจสอบ Docker อัตโนมัติ แสดงสถานะระบบ และมี 14 ตัวเลือก:

```
  1.  ติดตั้งระบบครั้งแรก
  2.  เริ่มระบบ
  3.  หยุดระบบ
  4.  รีสตาร์ทระบบ
  5.  เปิดหน้าเว็บในเบราว์เซอร์
  6.  ตรวจสถานะระบบ
  7.  ดู log ล่าสุด
  8.  สำรองข้อมูล
  9.  กู้คืนข้อมูล
 10.  รัน migration
 11.  แสดง IP สำหรับเครื่องอื่นใน LAN
 12.  โหลด Docker images จาก offline package
 13.  เปิดคู่มือติดตั้ง
 14.  ออกจากโปรแกรม
```

---

## เริ่มระบบ

```bat
offline\start.bat
```

## หยุดระบบ

```bat
offline\stop.bat
```

คำสั่งนี้ไม่ลบ Docker volumes และไม่ลบข้อมูล

## Restart ระบบ

```bat
offline\restart.bat
```

## เปิดเว็บ

บนเครื่องแม่ข่าย:

```text
http://localhost
```

จากเครื่องอื่นใน LAN:

```text
http://<IP เครื่องแม่ข่าย>
```

## วิธีหา IP เครื่องแม่ข่ายใน Windows

เปิด Command Prompt แล้วรัน:

```bat
ipconfig
```

ดูค่า `IPv4 Address` ของ network adapter ที่ต่อ LAN/Wi-Fi เช่น:

```text
IPv4 Address . . . . . . . . . . . : 192.168.1.25
```

เครื่องลูกข่ายจะเข้าเว็บด้วย:

```text
http://192.168.1.25
```

## Migration

รัน migration แบบเห็น log ชัดเจน:

```bat
offline\migrate.bat
```

หรือคำสั่งตรง:

```bat
docker compose run --rm backend alembic upgrade head
```

ระบบนี้ไม่ซ่อน destructive migration ไว้ใน startup script ของ backend container

## Backup

รัน:

```bat
offline\backup.bat
```

ผลลัพธ์จะอยู่ที่:

```text
data\backups\YYYYMMDD-HHMMSS\
```

ภายในจะมี:

- `database.sql` - PostgreSQL dump
- `source_data.tar.gz` - ไฟล์ต้นทาง/import source
- `uploads.tar.gz` - ไฟล์ upload
- `reports.tar.gz` - reports
- `logs.tar.gz` - logs
- `.env.bak` - สำเนา config สำหรับกู้คืนค่าเครื่องเดิม (มี secret ต้องเก็บปลอดภัย)

## Restore

Restore เป็น operation ที่ล้าง database เดิมก่อนนำ backup กลับมา จึงมี confirm prompt

```bat
offline\restore.bat data\backups\YYYYMMDD-HHMMSS
```

เมื่อ script ถาม ให้พิมพ์:

```text
RESTORE
```

ถ้าไม่ได้พิมพ์คำนี้ script จะยกเลิก

## ดู log

```bat
offline\logs.bat
```

ดูสถานะ service:

```bat
offline\status.bat
```

## Update version ใหม่

1. Backup ก่อนเสมอ:

```bat
offline\backup.bat
```

2. วาง source code หรือ image package version ใหม่
3. ถ้าเป็น source package ให้ build ใหม่:

```bat
docker compose build
```

4. รัน migration:

```bat
offline\migrate.bat
```

5. Start/restart:

```bat
offline\start.bat
```

## Offline image export/load

บนเครื่องที่มี internet:

```bat
offline\save-images.bat
```

ไฟล์ image จะถูกสร้างใน `images\`:

- `seamlessfordmis-backend.tar`
- `seamlessfordmis-frontend.tar`
- `postgres-16.tar`
- `nginx-alpine.tar`

นำ project folder พร้อม `images\` ไปยังเครื่อง offline แล้วรัน:

```bat
offline\load-images.bat
copy .env.offline.example .env
notepad .env
offline\start.bat
offline\migrate.bat
```

ถ้าเครื่อง offline ยังไม่เคยมี volume/database ให้รัน migration ก่อนใช้งานจริง

## Env vars สำคัญ

ตั้งค่าใน `.env`:

```env
POSTGRES_DB=seamlessfordmis
POSTGRES_USER=seamlessfordmis
POSTGRES_PASSWORD=CHANGE_ME_OFFLINE_DB_PASSWORD
DATABASE_URL=postgresql+psycopg://seamlessfordmis:CHANGE_ME_OFFLINE_DB_PASSWORD@db:5432/seamlessfordmis
APP_ENV=production
CORS_ORIGINS=http://localhost,http://127.0.0.1
SOURCE_DATA_DIR=/app/data
UPLOAD_DIR=/app/uploads/target_groups
REPORTS_DIR=/app/reports
BACKUP_DIR=/backups
NEXT_PUBLIC_API_BASE_URL=
TZ=Asia/Bangkok
```

อย่าใช้ password ตัวอย่างกับ production จริง

## Debug profile — เปิด port PostgreSQL ชั่วคราว

โดย default PostgreSQL ไม่เปิด port ออก host เพื่อความปลอดภัย
หากต้องการเชื่อมต่อด้วย DBeaver, pgAdmin, หรือ alembic CLI จากภายนอก container
ให้เปิด `debug` profile ซึ่งใช้ **socat relay** (ไม่ได้รัน Postgres ตัวที่สอง):

```bat
docker compose --profile debug up -d
```

จากนั้นเชื่อมต่อด้วย:

```text
Host:     127.0.0.1
Port:     5432  (หรือค่า POSTGRES_DEBUG_PORT ใน .env)
Database: seamlessfordmis
Username: seamlessfordmis
Password: (ค่าใน POSTGRES_PASSWORD)
```

หยุด relay เมื่อใช้งานเสร็จ:

```bat
docker compose --profile debug stop db-port-relay
```

> **⚠️ คำเตือน:** relay bind ที่ `127.0.0.1` เท่านั้น ห้ามเปลี่ยนเป็น `0.0.0.0` บน host ที่มีคนอื่นใช้ร่วม
> ห้ามเปิด `debug` profile ทิ้งไว้เป็นปกติในสภาพแวดล้อม production

---

## Volume strategy

- `seamlessfordmis_postgres_data` - PostgreSQL data
- `seamlessfordmis_source_data` - ไฟล์ต้นทาง/import source
- `seamlessfordmis_uploads` - ไฟล์ upload และ parsed cache
- `seamlessfordmis_reports` - report artifacts
- `seamlessfordmis_logs` - logs
- `./data/backups` - output backup บนเครื่องแม่ข่าย

PostgreSQL ไม่เปิด port `5432` ออก host โดย default เพื่อลดความเสี่ยง

## Checklist ก่อนใช้งานจริง (Production Readiness)

ทำ checklist นี้ให้ครบก่อนให้เจ้าหน้าที่ใช้งานจริง:

**ความปลอดภัยเบื้องต้น**
- [ ] เปลี่ยน `POSTGRES_PASSWORD` ใน `.env` แล้ว (ห้ามใช้ค่า default)
- [ ] `DATABASE_URL` ใน `.env` ใช้ password เดียวกับ `POSTGRES_PASSWORD`
- [ ] เครื่องแม่ข่ายมีรหัสผ่าน Windows และ lock screen
- [ ] folder project และ `data\backups\` จำกัดสิทธิ์เข้าถึงเฉพาะผู้ดูแล

**ระบบ**
- [ ] รัน `offline\healthcheck.bat` แล้วผ่านทุกรายการ
- [ ] เปิดเว็บได้จากเครื่องแม่ข่ายเองที่ `http://localhost`
- [ ] เปิดเว็บได้จากเครื่องลูกข่ายอื่นใน LAN ด้วย IP จริง
- [ ] รัน `offline\migrate.bat` แล้วเสร็จโดยไม่ error
- [ ] ตรวจสอบว่า port debug ปิดอยู่ — ไม่มี `db-port-relay` รันค้างอยู่

**ข้อมูลและ Backup**
- [ ] รัน `offline\backup.bat` ครั้งแรกแล้วสำเร็จ
- [ ] มีแผน backup สม่ำเสมอ (แนะนำทุกสัปดาห์หรือก่อน import ข้อมูลใหม่)
- [ ] เก็บ backup ไว้ที่ storage ที่แยกจากเครื่องแม่ข่าย
- [ ] ทดสอบ restore จาก backup แล้วสำเร็จอย่างน้อย 1 ครั้ง

**เอกสาร**
- [ ] แจ้งเจ้าหน้าที่ว่า URL หน้าเว็บคือ `http://<IP เครื่องแม่ข่าย>`
- [ ] มีผู้รับผิดชอบดูแล backup และ update ระบบ

---

## Troubleshooting

### Port 80 ถูกใช้

แก้ `.env`:

```env
HTTP_PORT=8080
```

แล้วรัน:

```bat
offline\restart.bat
```

เข้าเว็บที่:

```text
http://localhost:8080
```

### Docker ไม่รัน

เปิด Docker Desktop แล้วตรวจด้วย:

```bat
docker info
```

ถ้ายัง error ให้ restart เครื่องแม่ข่าย

### db unhealthy

ดู log:

```bat
docker compose logs --tail=100 db
```

ตรวจ `.env` ว่า `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, และ `DATABASE_URL` ตรงกัน

### backend migration fail

ดู log:

```bat
docker compose logs --tail=100 backend
offline\migrate.bat
```

ถ้า error เป็นเรื่อง database connection ให้ตรวจว่า `db` healthy ก่อน:

```bat
offline\status.bat
```

### frontend เปิดได้แต่ API ไม่มา

ตรวจ health:

```bat
curl http://localhost/health
curl http://localhost/api/screening-database/imports?limit=1
```

ตรวจว่า frontend build ใช้ same-origin API base:

```env
NEXT_PUBLIC_API_BASE_URL=
```

แล้ว build ใหม่:

```bat
docker compose build frontend
offline\restart.bat
```

## ข้อควรระวังข้อมูลส่วนบุคคล

- อย่าแชร์เครื่องแม่ข่ายออก internet โดยไม่จำเป็น
- ตั้งรหัสผ่านเครื่องแม่ข่ายและบัญชีผู้ใช้ให้เหมาะสม
- จำกัดสิทธิ์เข้าถึง folder project และ folder backup
- Backup สม่ำเสมอ และเก็บ backup อย่างปลอดภัย
- ไฟล์ patient/source data ไม่ควรถูก commit เข้า git
- ห้ามใส่ `.env` จริง, database dump, uploaded files, source files, หรือ backup เข้า Docker image หรือ repo

## วิธีติดตั้งผ่าน Windows Installer

สำหรับเครื่อง Windows ที่ต้องการติดตั้งแบบง่าย มี Windows Installer (`SeamlessFordMIS-Setup.exe`) ให้ใช้งาน
แทนการรัน `offline\install.bat` ด้วยตัวเอง

### ก่อนติดตั้ง

| รายการ | รายละเอียด |
|--------|-----------|
| OS | Windows 10 64-bit ขึ้นไป |
| Docker Desktop | ติดตั้งก่อน — [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop) |
| RAM | แนะนำ ≥ 8 GB |
| Disk | ≥ 20 GB (application + images + data) |
| สิทธิ์ | ต้องการ Administrator เพื่อสร้าง shortcut All Users |

> **หมายเหตุ**: ตัว installer ไม่ได้ bundle Docker Desktop — ต้องติดตั้ง Docker Desktop แยกต่างหากก่อน

### ขั้นตอนการติดตั้ง

1. รัน `SeamlessFordMIS-Setup.exe` ด้วยสิทธิ์ Administrator (คลิกขวา → Run as administrator)
2. ทำตามขั้นตอน Wizard — โปรแกรมจะถามเพียงปลายทางติดตั้ง (default: `C:\SeamlessFordMIS\app`)
3. Installer จะ:
   - คัดลอกไฟล์โปรแกรมทั้งหมดไปยัง `C:\SeamlessFordMIS\app\`
   - สร้างไฟล์ `.env` อัตโนมัติพร้อมรหัสผ่านสุ่ม 20 ตัวอักษร (เฉพาะเครื่องนี้)
   - สร้าง Desktop shortcuts: **SeamlessFordMIS - ควบคุมระบบ** และ **SeamlessFordMIS - เปิดเว็บ**
   - สร้าง Start Menu group: **SeamlessFordMIS**
   - แสดงผล Docker check — หาก Docker ยังไม่พร้อมจะแจ้งให้ทราบ
4. หน้าสุดท้ายของ Wizard เสนอให้ run `post-install-check.bat` และเปิดคู่มือนี้

### หลังติดตั้ง — เริ่มใช้งานครั้งแรก

1. ดับเบิลคลิก Desktop shortcut **SeamlessFordMIS - ควบคุมระบบ**
2. เลือก `[1] ติดตั้ง / เริ่มระบบครั้งแรก (install + start)` — ระบบจะ load Docker images, migrate database, และ start services
3. รอจนระบบ start สำเร็จ แล้วเลือก `[5] เปิดเว็บแอป` หรือดับเบิลคลิก **SeamlessFordMIS - เปิดเว็บ**
4. เว็บแอปจะเปิดที่ `http://localhost` (หรือ port ที่กำหนดใน `.env`)

### ไฟล์ที่ installer สร้าง

```
C:\SeamlessFordMIS\
  app\                    ← ไฟล์โปรแกรมทั้งหมด (ถูกลบตอน uninstall)
    docker-compose.yml
    alembic.ini
    .env                  ← รหัสผ่าน random สำหรับเครื่องนี้โดยเฉพาะ
    offline\              ← scripts ทั้งหมด (control-panel, start, stop ฯลฯ)
    alembic\              ← database migration scripts
    docker\               ← Dockerfile build context
    OFFLINE_INSTALL.md
    docs\
  data\                   ← ข้อมูลผู้ป่วย และ backup (ไม่ถูกลบตอน uninstall)
    backups\
  logs\                   ← application logs (ไม่ถูกลบตอน uninstall)
    images\               ← Docker image tarballs (ถ้ามี offline package)
```

### การอัปเดตระบบ

1. สำรองข้อมูลก่อนอัปเดตทุกครั้ง — รัน `offline\pre-update-backup.bat`
2. รัน installer เวอร์ชันใหม่ทับได้เลย — ไฟล์ `.env` เดิมจะถูกเก็บไว้ (รหัสผ่านไม่เปลี่ยน)
3. หลังติดตั้งเสร็จ เปิด Control Panel → เลือก `[10] รัน database migration`

> **หมายเหตุ upgrade-safe**: Installer จะสร้าง `.env` ใหม่เฉพาะถ้าไม่มีไฟล์ `.env` อยู่แล้ว
> ถ้ามีอยู่แล้ว จะข้ามการสร้างทั้งหมด — รหัสผ่านฐานข้อมูลและ config จะยังเหมือนเดิม

### การถอนการติดตั้ง

ถอนการติดตั้งผ่าน Control Panel → Programs and Features → SeamlessFordMIS → Uninstall

**สิ่งที่ถูกลบ:**
- ไฟล์โปรแกรมใน `C:\SeamlessFordMIS\app\`
- Desktop shortcuts และ Start Menu group
- หยุด Docker containers ก่อนลบ (graceful stop — ไม่ลบ volumes)

**สิ่งที่ไม่ถูกลบ (ต้องลบเองถ้าต้องการ):**
- ข้อมูลผู้ป่วยใน Docker volumes
- ข้อมูลสำรองใน `C:\SeamlessFordMIS\data\`
- Logs ใน `C:\SeamlessFordMIS\logs\`

> รายละเอียดนโยบายข้อมูลฉบับเต็ม: [`docs/INSTALLER_DATA_SAFETY.md`](docs/INSTALLER_DATA_SAFETY.md)

### การลบข้อมูลทั้งหมด (กรณีต้องการ)

> ⚠️ **คำเตือน**: การดำเนินการนี้ไม่สามารถย้อนกลับได้ — ข้อมูลผู้ป่วยทั้งหมดจะถูกลบถาวร

1. ถอนการติดตั้งโปรแกรมก่อน (ขั้นตอนด้านบน)
2. ไปที่ `C:\SeamlessFordMIS\app\offline\`
3. เปลี่ยนชื่อไฟล์ `danger-remove-all-data.bat.example` → `danger-remove-all-data.bat`
4. รันไฟล์ด้วยสิทธิ์ Administrator
5. พิมพ์ยืนยัน 3 ขั้นตอนตามที่ระบบถาม

---

## Linux/macOS

> **หมายเหตุ:** ระบบนี้ออกแบบมาเพื่อ Windows เป็นหลัก — scripts สำหรับ Linux/macOS เป็น POSIX sh
> ที่มีพฤติกรรมเทียบเท่ากัน แต่มีรายละเอียดที่แตกต่างกันบางส่วน (ดูตาราง [ความแตกต่าง](#ความแตกต่าง-bat-vs-sh) ด้านล่าง)

### ข้อกำหนดเบื้องต้น (Linux/macOS)

- **Docker Engine** และ **Docker Compose plugin** ติดตั้งอยู่และเริ่มทำงานแล้ว
- **curl** ติดตั้งอยู่ (ใช้ในการตรวจสอบ web endpoint)
- Shell: `/bin/sh` POSIX-compatible (bash, dash, zsh ใช้ได้ทั้งหมด)

### Script ทั้งหมด

| Script | คำอธิบาย | เทียบกับ Windows |
|---|---|---|
| `offline/install.sh` | ติดตั้งและเริ่มระบบครั้งแรก | `install.bat` |
| `offline/start.sh` | เริ่ม containers | `start.bat` |
| `offline/stop.sh` | หยุด containers | `stop.bat` |
| `offline/backup.sh` | สำรองข้อมูลปัจจุบัน | `backup.bat` |
| `offline/restore.sh` | กู้คืนจาก backup | `restore.bat` |
| `offline/healthcheck.sh` | ตรวจสอบสุขภาพระบบ | `healthcheck.bat` |
| `offline/post-install-check.sh` | ตรวจสอบระบบหลังติดตั้ง (7 รายการ) | `post-install-check.bat` |
| `offline/open-web.sh` | เปิดเบราว์เซอร์ไปยังระบบ | `open-web.bat` |
| `offline/pre-update-backup.sh` | สำรองข้อมูลก่อนอัปเดต | `pre-update-backup.bat` |
| `offline/danger-remove-all-data.sh.example` | ลบข้อมูลทั้งหมด (ต้อง rename ก่อน) | `danger-remove-all-data.bat.example` |

### การใช้งานพื้นฐาน

```sh
# ติดตั้งครั้งแรก
sh offline/install.sh

# เริ่ม / หยุด ระบบ
sh offline/start.sh
sh offline/stop.sh

# ตรวจสอบระบบ
sh offline/post-install-check.sh   # 7 รายการ (Docker, .env, images, containers, DB, web)
sh offline/healthcheck.sh          # ตรวจสอบสั้นๆ

# เปิดเว็บ
sh offline/open-web.sh             # macOS: open, Linux: xdg-open, fallback: พิมพ์ URL

# สำรองข้อมูล
sh offline/backup.sh
sh offline/pre-update-backup.sh    # สำรองก่อนอัปเดต (แนะนำทุกครั้งก่อนอัปเกรด)

# กู้คืน
sh offline/restore.sh data/backups/pre-update-YYYYMMDD-HHMMSS
```

### ลบข้อมูลทั้งหมด (ใช้ด้วยความระมัดระวัง)

```sh
# ต้อง rename ก่อน — .example จะรันไม่ได้โดยตรง
mv offline/danger-remove-all-data.sh.example offline/danger-remove-all-data.sh
chmod +x offline/danger-remove-all-data.sh

# รัน (ต้องยืนยัน 3 ขั้นตอน)
sh offline/danger-remove-all-data.sh
```

> ⚠️ **คำเตือน**: ขั้นตอนการยืนยัน — พิมพ์ `YES` → พิมพ์ `DELETE ALL PATIENT DATA` (ตัวพิมพ์ใหญ่ทุกตัว) → รอนับถอยหลัง 10 วินาที (กด Ctrl+C เพื่อยกเลิก)

### Exit codes ของ `post-install-check.sh`

| Exit code | ความหมาย |
|---|---|
| `0` | ทุกรายการผ่าน (ระบบพร้อมใช้งานสมบูรณ์) |
| `1` | มีรายการที่ไม่ผ่าน (FAIL) — ต้องแก้ไข |
| `2` | ผ่านแต่มีคำเตือน — ปกติหมายความว่า containers ยังไม่ได้เริ่ม ให้รัน `install.sh` ก่อน |

---

## ความแตกต่าง .bat vs .sh

Scripts สำหรับ Windows (`.bat`) และ Linux/macOS (`.sh`) มีพฤติกรรมเทียบเท่ากัน แต่ implementation แตกต่างกันในรายละเอียดต่อไปนี้:

### การรับ input จากผู้ใช้

| สถานการณ์ | Windows (.bat) | Linux/macOS (.sh) |
|---|---|---|
| Yes/No prompt | `choice /C YN /M "..."` — รับตัวอักษรเดียว ไม่ต้องกด Enter | `printf "...(y/N): "; read -r CHOICE; case "$CHOICE" in y\|Y) ...` — ต้องกด Enter |
| พิมพ์คำยืนยัน | `set /P VAR=พิมพ์:` | `printf "พิมพ์: "; read -r VAR` |
| ซ่อน input (password) | ไม่มีใน native .bat | `stty -echo; read -r VAR; stty echo` |

### การตรวจสอบ web endpoint

| หัวข้อ | Windows (.bat) | Linux/macOS (.sh) |
|---|---|---|
| เครื่องมือ | `PowerShell -Command "Invoke-WebRequest -Uri ... -UseBasicParsing"` | `curl -s -o /dev/null -w "%{http_code}" --max-time 5 URL` |
| fallback | ไม่มี curl fallback บน Windows รุ่นเก่า | `if ! command -v curl` → แสดง WARN แทน |
| timeout | `TimeoutSec=5` ใน PowerShell | `--max-time 5` ใน curl |

### การสร้าง timestamp

| หัวข้อ | Windows (.bat) | Linux/macOS (.sh) |
|---|---|---|
| คำสั่ง | `PowerShell -Command "Get-Date -Format 'yyyyMMdd-HHmmss'"` | `date +%Y%m%d-%H%M%S` |
| ผลลัพธ์ | `20260522-143000` | `20260522-143000` (เหมือนกัน) |
| timezone | ตาม Windows system locale | ตาม system locale |

### การเปิดเบราว์เซอร์

| หัวข้อ | Windows (.bat) | Linux/macOS (.sh) |
|---|---|---|
| คำสั่ง | `start "" "http://localhost"` | macOS: `open URL`, Linux: `xdg-open URL` |
| fallback | ไม่มี (ทุก Windows รุ่นมี `start`) | `sensible-browser URL` → พิมพ์ URL ออกมา |
| background | เปิด browser ใน background เสมอ | `xdg-open ... &` (non-blocking) |

### การตรวจสอบ container status

| หัวข้อ | Windows (.bat) | Linux/macOS (.sh) |
|---|---|---|
| คำสั่ง | `docker compose ps --filter "status=running"` + `findstr` | `docker compose ps --services --filter "status=running"` + `grep -qi "^svc$"` |
| case sensitivity | `findstr /I` (case-insensitive) | `grep -qi` (case-insensitive) |

### สิ่งที่เหมือนกันทุกประการ

- **Docker commands**: `docker compose up/down/ps/exec/logs/volume` — เหมือนกัน 100%
- **ชื่อ Docker volumes**: `seamlessfordmis_*` — เหมือนกัน
- **คำยืนยัน 3 ขั้นตอน** ของ danger-remove: `YES` → `DELETE ALL PATIENT DATA` → นับถอยหลัง 10 วินาที
- **Backup structure**: `data/backups/YYYY-YYYYMMDD-HHMMSS/` + ไฟล์เดียวกัน
- **Restore confirmation**: ต้องพิมพ์ `RESTORE` (ตัวพิมพ์ใหญ่ทุกตัว)
- **Exit codes** ของ post-install-check: 0/1/2 เหมือนกัน
- **Port**: อ่านจาก `.env` → `HTTP_PORT` เหมือนกัน

## Build installer สำหรับทีม IT / build machine

ใช้คำสั่งเหล่านี้บนเครื่อง Windows ที่มี Python, Docker Desktop และ Inno Setup 6:

```bat
installer\build-installer.bat check
installer\build-installer.bat dev
installer\build-installer.bat offline-full
```

- `check` ตรวจ dependency และไฟล์ที่จำเป็น แต่ยังไม่สร้าง installer
- `dev` สร้าง installer แบบไม่ require image tarballs เหมาะกับการทดสอบหรือกรณีแจก images แยกเท่านั้น
- `offline-full` ต้องมี `images\postgres-16.tar`, `images\nginx-alpine.tar`, `images\seamlessfordmis-backend.tar`, `images\seamlessfordmis-frontend.tar` ครบก่อน build และเป็น mode สำหรับแจกจ่ายเครื่อง offline จริง

ถ้าใช้ Windows Installer แบบ offline-full ไฟล์ images จะถูกติดตั้งไว้ที่ `C:\SeamlessFordMIS\app\images\`
