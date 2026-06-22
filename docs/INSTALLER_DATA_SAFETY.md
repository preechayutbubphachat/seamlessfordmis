# SeamlessFordMIS — นโยบายความปลอดภัยข้อมูลสำหรับ Windows Installer

> เอกสารนี้อธิบายการออกแบบ Windows Installer ในส่วนที่เกี่ยวกับการปกป้องข้อมูลผู้ป่วย  
> อ้างอิง: พ.ร.บ. คุ้มครองข้อมูลส่วนบุคคล (PDPA) และมาตรฐานความปลอดภัยข้อมูลโรงพยาบาล

---

## หลักการออกแบบ

SeamlessFordMIS Installer ถูกออกแบบโดยยึดหลัก **ข้อมูลผู้ป่วยต้องไม่ถูกลบโดยไม่ตั้งใจ** เป็นสำคัญ

### 1. Installer ไม่รวมข้อมูลใดๆ

Installer (`SeamlessFordMIS-Setup.exe`) ประกอบด้วย:
- ✅ ไฟล์โปรแกรม (scripts, config templates, Docker images)
- ❌ ไม่มีข้อมูลผู้ป่วย
- ❌ ไม่มี `.env` จริง หรือรหัสผ่านจริง
- ❌ ไม่มี database dump
- ❌ ไม่มีไฟล์ที่ผู้ใช้อัปโหลด

### 2. รหัสผ่านฐานข้อมูลสร้างใหม่ต่อเครื่อง

รหัสผ่าน `POSTGRES_PASSWORD` สร้างแบบสุ่ม 20 ตัวอักษรระหว่างการติดตั้ง โดย Inno Setup Pascal Script  
รหัสผ่านนี้แตกต่างกันในแต่ละเครื่อง และไม่มีการส่งออกนอกเครื่อง

ไฟล์ `.env` ที่สร้างมีรูปแบบดังนี้:
```
POSTGRES_PASSWORD=<random-20-chars>
DATABASE_URL=postgresql+psycopg://seamlessfordmis:<same-password>@db:5432/seamlessfordmis
```

### 3. Upgrade-safe — รหัสผ่านเดิมถูกรักษาไว้

หาก `.env` มีอยู่แล้วในเครื่อง (กรณี reinstall หรือ upgrade) Installer จะ **ไม่สร้าง `.env` ใหม่**  
ฐานข้อมูลเดิมและข้อมูลผู้ป่วยจะยังคงเข้าถึงได้ด้วยรหัสผ่านเดิม

---

## นโยบาย Uninstall

### สิ่งที่ Uninstaller ทำ

| การกระทำ | เหตุผล |
|---|---|
| หยุด Docker containers (`docker compose stop`) | ป้องกัน data corruption ระหว่างลบไฟล์ |
| ลบไฟล์โปรแกรมใน `C:\SeamlessFordMIS\app\` | คืนพื้นที่ disk |
| ลบ Shortcuts บน Desktop และ Start Menu | ทำความสะอาด UI |

### สิ่งที่ Uninstaller ไม่ทำ (จงใจ)

| สิ่งที่ไม่ลบ | เหตุผล |
|---|---|
| Docker volumes (`seamlessfordmis_*`) | มีข้อมูลผู้ป่วย — ต้องการการยืนยันจากผู้บริหาร |
| `C:\SeamlessFordMIS\data\backups\` | ข้อมูลสำรอง — มีคุณค่าทางกฎหมายและการตรวจสอบ |
| `C:\SeamlessFordMIS\logs\` | Audit trail — อาจจำเป็นสำหรับการสืบสวนในอนาคต |

Uninstaller แสดง dialog ยืนยันก่อนดำเนินการ โดยระบุชัดเจนว่า:
- ลบอะไรบ้าง
- ไม่ลบอะไรบ้าง
- วิธีลบข้อมูลถ้าต้องการ (ต้องทำด้วยตนเองผ่าน `danger-remove-all-data.bat.example`)

---

## การลบข้อมูลถาวร (ต้องการการอนุมัติ)

หากต้องการลบข้อมูลผู้ป่วยทั้งหมดออกจากระบบ ต้องดำเนินการด้วยตนเองผ่าน:

```
C:\SeamlessFordMIS\app\offline\danger-remove-all-data.bat.example
```

> **ไฟล์นี้มีนามสกุล `.bat.example` โดยจงใจ**  
> ต้องเปลี่ยนชื่อเป็น `.bat` ด้วยตนเองก่อนจึงจะรันได้

ขั้นตอนการยืนยัน 3 ชั้น:
1. พิมพ์ `YES` เพื่อยืนยันว่าต้องการลบข้อมูล
2. พิมพ์ข้อความ `DELETE ALL PATIENT DATA` ให้ตรงทุกตัวอักษร (case-sensitive)
3. นับถอยหลัง 10 วินาที (กด Ctrl+C เพื่อยกเลิก)

### เงื่อนไขการใช้งาน

สคริปต์นี้ควรใช้เฉพาะเมื่อ:
- ล้างระบบเพื่อทดสอบใหม่ทั้งหมดในสภาพแวดล้อม dev/test
- ถอนการติดตั้งระบบและต้องการลบข้อมูลออกทุกอย่าง
- **ได้รับอนุญาตเป็นลายลักษณ์อักษรจากผู้บริหารโรงพยาบาลก่อนเสมอ**

---

## ที่เก็บข้อมูลผู้ป่วย

| ที่เก็บ | ประเภทข้อมูล | วิธีสำรอง |
|---|---|---|
| Docker volume `seamlessfordmis_postgres_data` | ฐานข้อมูล PostgreSQL (ข้อมูลทั้งหมด) | `pg_dump` ผ่าน `backup.bat` |
| Docker volume `seamlessfordmis_source_data` | ไฟล์ต้นทางที่นำเข้า | `tar.gz` ผ่าน `backup.bat` |
| Docker volume `seamlessfordmis_uploads` | ไฟล์ที่ผู้ใช้อัปโหลด | `tar.gz` ผ่าน `backup.bat` |
| Docker volume `seamlessfordmis_reports` | รายงานที่สร้างแล้ว | `tar.gz` ผ่าน `backup.bat` |
| `C:\SeamlessFordMIS\data\backups\` | ไฟล์สำรองข้อมูล | เก็บในพื้นที่ปลอดภัย |

---

## คำแนะนำด้านความปลอดภัย

### การจัดการ `.env`

```
C:\SeamlessFordMIS\app\.env
```

- ไฟล์นี้มีรหัสผ่านฐานข้อมูล
- **ห้ามแชร์ผ่าน email, Line, หรือ cloud storage**
- **ห้ามบันทึกลง version control (git)**
- ถ้าสงสัยว่ารหัสผ่านรั่วไหล ให้เปลี่ยนรหัสผ่านและ restart containers

### การสำรองข้อมูล

- สำรองข้อมูลเป็นประจำผ่าน `offline\backup.bat` หรือ Control Panel ข้อ 4
- ข้อมูลสำรองต้องเก็บในพื้นที่ปลอดภัยภายในหน่วยงาน
- **ห้ามส่งออกนอกเครือข่ายโรงพยาบาล**
- **ห้าม upload ขึ้น cloud สาธารณะ** (Google Drive, Dropbox, OneDrive ทั่วไป)

### ก่อนอัปเดตระบบ

รัน `offline\pre-update-backup.bat` ก่อนอัปเดตทุกครั้ง เพื่อให้มีข้อมูลสำรองไว้กู้คืนหากเกิดปัญหา

---

## Audit Trail

ทุก action ที่เกิดขึ้นในระบบถูก log ไว้ใน:
- Docker volume `seamlessfordmis_logs` — application logs
- `C:\SeamlessFordMIS\logs\` — system-level logs

Log files เหล่านี้ไม่ถูกลบโดย Uninstaller และสามารถใช้เป็นหลักฐานการตรวจสอบได้

---

*เอกสารนี้เป็นส่วนหนึ่งของ SeamlessFordMIS — ระบบคัดกรองโรค โรงพยาบาลหนองพอก*
