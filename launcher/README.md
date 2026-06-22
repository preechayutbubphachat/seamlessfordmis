# SeamlessFordMIS — GUI Launcher

GUI Launcher สำหรับควบคุม SeamlessFordMIS บน Windows  
สร้างด้วย Python 3.10+ + CustomTkinter + PyInstaller

---

## ภาพรวม

Launcher เป็น GUI wrapper สำหรับ `offline/*.bat` scripts ที่มีอยู่แล้ว  
**ไม่ได้เขียน web app ใหม่** — เพียงให้ UI กราฟิกสำหรับ hospital staff ที่ไม่คุ้นเคย command line

### ฟีเจอร์

| ส่วน | รายละเอียด |
|---|---|
| Header | ชื่อระบบ + badge "Local / ภายในหน่วยงาน" |
| Status Area | Docker / ฐานข้อมูล / Backend / Frontend / nginx / URL — สีเขียว/เหลือง/แดง/เทา |
| Action Buttons | Start, Stop, Restart, เปิดเว็บ, Status, Logs, Backup, Restore, Migration, Load Images, LAN IP, Health Check |
| Guide | เปิด `OFFLINE_INSTALL.md` จากหน้า Launcher |
| Log Panel | Streaming output จาก scripts, Clear, Copy — **password ถูกซ่อนทุกกรณีก่อนแสดงและก่อน copy** |
| Warning Area | แจ้งเตือน Docker ไม่ทำงาน / service มีปัญหา |

### ความปลอดภัย

- ไม่แสดง password จาก `.env` ในทุกกรณี (scrub ด้วย regex ก่อนแสดง)
- ไม่ upload ข้อมูลใดออกอินเทอร์เน็ต — ทุก call เป็น `http://localhost`
- Restore ต้องผ่านหน้าต่าง Command Prompt แยก — ต้องพิมพ์ `RESTORE` ด้วยตัวเอง
- ทุก action รันผ่าน `offline/*.bat` เดิม ไม่มี logic พิเศษที่อาจข้าม safety guard

---

## Requirements

- Python 3.10 หรือใหม่กว่า
- Windows 10/11 64-bit
- Docker Desktop ติดตั้งและทำงานแล้ว

---

## วิธี Build EXE

```bat
cd launcher
build-launcher.bat
```

Script จะ:
1. ตรวจ Python version (ต้องการ 3.10+)
2. `pip install -r requirements.txt` (customtkinter, pillow, requests, psutil)
3. `pip install pyinstaller`
4. รัน PyInstaller `--onefile --noconsole`
5. คัดลอก EXE ออกมาที่ `launcher\SeamlessFordMIS-Launcher.exe`

**ขนาด output:** ประมาณ 50–80 MB (Python runtime bundled)

### หมายเหตุ Antivirus

PyInstaller bundle อาจถูก Antivirus บางตัว flag เป็น false positive  
ถ้าพบปัญหา ให้เพิ่ม exception สำหรับ `SeamlessFordMIS-Launcher.exe` ใน Antivirus settings

---

## วิธีใช้งาน

### วิธีที่ 1: ผ่าน Installer (แนะนำ)

รัน `installer\build-installer.bat` — installer จะถามว่าต้องการ build launcher ก่อนหรือไม่  
หลัง install: ดับเบิลคลิก Desktop shortcut **SeamlessFordMIS**

### วิธีที่ 2: วางไฟล์เอง

1. Build EXE ตามขั้นตอนด้านบน
2. วาง `SeamlessFordMIS-Launcher.exe` ใน `C:\SeamlessFordMIS\app\`
3. ดับเบิลคลิก EXE

### วิธีที่ 3: Dev mode (ไม่ต้อง build)

```bat
cd C:\SeamlessFordMIS\app\launcher
pip install -r requirements.txt
python seamlessfordmis_launcher.py
```

---

## Working Directory

Launcher ต้องการ `docker-compose.yml` ในโฟลเดอร์เดียวกันหรือ parent  
ลำดับการค้นหา:
1. โฟลเดอร์ที่ EXE อยู่
2. Parent ของโฟลเดอร์ EXE
3. Current working directory

ถ้าไม่พบ `docker-compose.yml` จะแสดง error message และออก

---

## โครงสร้างไฟล์

```
launcher/
  seamlessfordmis_launcher.py   ← source code หลัก
  requirements.txt              ← Python dependencies
  build-launcher.bat            ← build script
  README.md                     ← เอกสารนี้
  (SeamlessFordMIS-Launcher.exe)← output หลัง build (ไม่ commit ใน git)
  dist/                         ← PyInstaller output (ไม่ commit ใน git)
  build/                        ← PyInstaller temp (ไม่ commit ใน git)
```

---

## ข้อจำกัดที่รู้อยู่

| ข้อจำกัด | เหตุผล |
|---|---|
| Windows เท่านั้น | `offline/*.bat` ใช้ cmd.exe / Windows batch syntax |
| ต้องการ Docker Desktop ก่อน | Launcher ไม่ติดตั้ง Docker ให้ |
| Restore เปิด cmd window แยก | ต้องรับ typed confirmation "RESTORE" จากผู้ใช้ |
| AV อาจ flag PyInstaller EXE | false positive — เพิ่ม exception ใน AV settings |
| ยังไม่ได้ทดสอบ Windows Clean VM | ดู `installer/WINDOWS_CLEAN_VM_TEST.md` |
| สถานะ production-ready | ยังไม่ claim จนกว่าจะผ่าน Windows Clean VM test จริง |

## สถานะ build ปัจจุบัน

- Launcher source-ready และ binary-built: `launcher\SeamlessFordMIS-Launcher.exe`
- Installer build script เรียกได้ด้วย `installer\build-installer.bat dev` หรือ `installer\build-installer.bat offline-full`
- ถ้าไม่มี Launcher EXE script จะ build launcher ก่อน และถ้า launcher build fail จะหยุด build installer
- `offline-full` ต้องมี Docker image tarballs ครบก่อน build installer สำหรับเครื่อง offline จริง
- Windows Clean VM verification ยัง pending จึงห้าม claim ว่า production-ready

---

*SeamlessFordMIS — ระบบคัดกรองโรค โรงพยาบาลหนองพอก*
