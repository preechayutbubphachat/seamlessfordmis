# GUI Launcher — SeamlessFordMIS

> **สถานะ:** ✅ **Implemented** — Phase 2 (Python CustomTkinter) ดำเนินการแล้ว 2026-05-26
> **วันที่เขียน:** 2026-05-22
> **อัปเดต:** 2026-05-26 — Phase 2 implemented: `launcher/seamlessfordmis_launcher.py`
> **Phase ปัจจุบัน:** Phase 2 — GUI Launcher (Python CustomTkinter) พร้อมใช้งาน

---

## บริบทและปัญหา

ระบบ SeamlessFordMIS ในโหมด offline/LAN ปัจจุบันควบคุมผ่าน `offline/control-panel.bat` ซึ่งแสดงเมนูข้อความใน Command Prompt บน Windows เจ้าหน้าที่โรงพยาบาลที่ไม่คุ้นเคยกับ command line อาจรู้สึกไม่สะดวก และเมนูข้อความมีข้อจำกัดในการแสดงผลสถานะแบบ real-time

เอกสารนี้เปรียบเทียบตัวเลือก GUI launcher สำหรับ Windows และให้ข้อเสนอแนะแบบ phased approach

---

## ตัวเลือกที่พิจารณา

### ตัวเลือก 1: .NET WinForms / WPF (C#)

**คำอธิบาย:** พัฒนา desktop app ด้วย C# ใช้ WinForms หรือ WPF framework ซึ่งเป็น native Windows technology

| หัวข้อ | รายละเอียด |
|---|---|
| Runtime | .NET 6/8 (ต้องติดตั้งหรือ bundle) |
| ขนาด binary | ~50–150 MB (self-contained) |
| ภาษาที่ใช้ | C# |
| ความยากในการพัฒนา | ปานกลาง (ต้องรู้ C# และ .NET) |
| การ distribute | ต้องการ .NET runtime หรือ publish self-contained |
| ทำงานบน Linux/macOS | ❌ WinForms/WPF: Windows เท่านั้น |

**ข้อดี:**
- Native Windows — ดูเหมือนโปรแกรม Windows ของแท้
- เข้าถึง Windows API ได้เต็มที่ (System Tray, Windows Notifications)
- ไม่ต้องการ browser runtime
- Microsoft สนับสนุนระยะยาว

**ข้อเสีย:**
- ต้องพัฒนาใหม่ทั้งหมดด้วย C# — ต้องการผู้พัฒนาที่รู้ .NET
- ถ้าทีมไม่มีประสบการณ์ C# ต้องเรียนรู้ก่อน
- ไม่ re-use code จาก frontend (Next.js) ที่มีอยู่แล้ว
- UI สวยงามต้องใช้ WPF + XAML ซึ่งมี learning curve

**เหมาะกับโปรเจคนี้:** ✅ ถ้ามีทรัพยากร .NET dev

---

### ตัวเลือก 2: Tauri (Rust + Web Frontend)

**คำอธิบาย:** Tauri ใช้ Web frontend (HTML/CSS/JS) สำหรับ UI และ Rust สำหรับ backend logic เป็น framework ที่ได้รับความนิยมสูงขึ้นเรื่อยๆ

| หัวข้อ | รายละเอียด |
|---|---|
| Runtime | ไม่ต้องการ — ใช้ OS WebView (Microsoft Edge WebView2 บน Windows) |
| ขนาด binary | ~3–15 MB (เล็กมาก) |
| ภาษาที่ใช้ | Rust (backend) + HTML/CSS/JS (frontend) |
| ความยากในการพัฒนา | สูง (Rust มี learning curve ชัน) |
| การ distribute | Single .exe หรือ .msi |
| ทำงานบน Linux/macOS | ✅ Cross-platform |

**ข้อดี:**
- Binary เล็กมาก
- Web frontend — สามารถ re-use style จาก Next.js frontend บางส่วนได้
- ไม่ต้องการ Node.js runtime ในเครื่องผู้ใช้
- Cross-platform (ถ้าต้องการ macOS/Linux ด้วยในอนาคต)
- Security model ดี (Rust memory safety)

**ข้อเสีย:**
- Rust มี learning curve สูงมาก — ถ้าทีมไม่รู้ Rust ต้องใช้เวลานาน
- WebView2 ต้องติดตั้งบน Windows 10 รุ่นเก่า (Windows 11 มาพร้อมแล้ว)
- Ecosystem ยังเล็กกว่า Electron
- Debugging ยากกว่า Electron

**เหมาะกับโปรเจคนี้:** ⚠️ เฉพาะถ้ามีทีมที่รู้ Rust หรือยอมรับ time investment สูง

---

### ตัวเลือก 3: Electron (Node.js + Chromium)

**คำอธิบาย:** Electron รัน Node.js + Chromium ใน desktop app เป็น framework ที่ VS Code, Slack, Discord ใช้

| หัวข้อ | รายละเอียด |
|---|---|
| Runtime | Bundle Chromium + Node.js |
| ขนาด binary | ~120–200 MB |
| ภาษาที่ใช้ | JavaScript/TypeScript |
| ความยากในการพัฒนา | ต่ำ–ปานกลาง (ถ้ารู้ JS อยู่แล้ว) |
| การ distribute | .exe ไฟล์เดียวหรือ installer |
| ทำงานบน Linux/macOS | ✅ Cross-platform |

**ข้อดี:**
- ทีมที่รู้ JavaScript/TypeScript (Next.js) สามารถพัฒนาได้ทันที
- Ecosystem ใหญ่ที่สุด — ตัวอย่างและ library มาก
- UI ทำได้สวยงามด้วย CSS
- Dev tools ดีมาก (Chrome DevTools)

**ข้อเสีย:**
- **Binary ใหญ่มาก** — 120–200 MB เฉพาะ launcher เปล่า
- Memory consumption สูง (Chromium ใช้ RAM มาก)
- ไม่เหมาะสำหรับ utility เล็กๆ เช่น launcher
- ถูกวิจารณ์เรื่อง performance และขนาด

**เหมาะกับโปรเจคนี้:** ⚠️ Binary ใหญ่เกินไปสำหรับ launcher — อาจรับได้ถ้าทีมเป็น JS เท่านั้น

---

### ตัวเลือก 4: Python + Tkinter (หรือ PySimpleGUI / CustomTkinter)

**คำอธิบาย:** Python มี GUI library ในตัว (Tkinter) และมีตัวเลือกที่ทันสมัยกว่าอย่าง CustomTkinter

| หัวข้อ | รายละเอียด |
|---|---|
| Runtime | Python 3.x (ต้องติดตั้ง หรือ bundle ด้วย PyInstaller) |
| ขนาด binary | ~30–80 MB (PyInstaller bundle) |
| ภาษาที่ใช้ | Python |
| ความยากในการพัฒนา | ต่ำ (ถ้ารู้ Python อยู่แล้ว) |
| การ distribute | .exe ผ่าน PyInstaller หรือ Nuitka |
| ทำงานบน Linux/macOS | ✅ Cross-platform |

**ข้อดี:**
- Backend ของโปรเจคนี้เขียนด้วย Python (FastAPI) — ทีมรู้ Python อยู่แล้ว
- พัฒนาเร็ว, prototyping ง่าย
- Tkinter อยู่ใน stdlib ไม่ต้องติดตั้งเพิ่ม
- CustomTkinter ทำ UI สมัยใหม่ได้

**ข้อเสีย:**
- Tkinter มี UI เก่า — ต้องใช้ CustomTkinter เพื่อให้ดูทันสมัย
- PyInstaller bundle อาจมีปัญหา false positive จาก antivirus
- Python startup time ช้ากว่า native app
- ไม่สามารถเข้าถึง Windows API ขั้นสูงได้เท่า .NET

**เหมาะกับโปรเจคนี้:** ✅ ถ้าทีมเป็น Python และต้องการ prototype เร็ว

---

## ตารางเปรียบเทียบ

| หัวข้อ | .NET WinForms/WPF | Tauri | Electron | Python Tkinter |
|---|---|---|---|---|
| ขนาด binary | ~100 MB | ~5–15 MB | ~150–200 MB | ~40–80 MB |
| ความยากพัฒนา | ปานกลาง | สูงมาก | ต่ำ (JS) | ต่ำ (Python) |
| Native look | ✅ ดีที่สุด | ✅ ดี | ⚠️ Chromium | ⚠️ พื้นฐาน |
| System Tray | ✅ | ✅ | ✅ | ⚠️ จำกัด |
| Cross-platform | ❌ | ✅ | ✅ | ✅ |
| Reuse โค้ดที่มี | ❌ | ⚠️ บาง | ⚠️ JS | ✅ Python |
| Runtime overhead | ต่ำ | ต่ำมาก | สูง (Chromium) | ต่ำ–ปานกลาง |
| Windows 10 compat | ✅ | ⚠️ WebView2 | ✅ | ✅ |
| ความเสถียร | สูงมาก | สูง | สูง | ปานกลาง |

---

## ข้อเสนอแนะ — Phased Approach

### Phase 1 (ปัจจุบัน): คง `control-panel.bat` ไว้

**เหตุผล:**
- `control-panel.bat` ทำงานได้ดีและเสถียรแล้ว
- ไม่ต้องการ dependency เพิ่มเติม
- ทุกคนที่ install Windows มี Command Prompt
- ลด scope ของ MVP installer ให้เล็กที่สุดก่อน
- ควรรอดูว่า user feedback จริงๆ บอกว่า .bat เป็นปัญหาก่อน

**สิ่งที่ควรปรับปรุงใน Phase 1 ก่อน (ถ้าต้องการ):**
- เพิ่ม color ใน .bat output ด้วย `color` command
- เพิ่ม shortcut บน Desktop ที่เรียก `control-panel.bat` โดยตรง
- ใส่ icon ที่ shortcut ให้ดูเป็น professional

### Phase 2 (ถ้าต้องการ GUI จริงๆ): Python + CustomTkinter

**เหตุผล:**
- ทีมมี Python skill อยู่แล้วจาก backend
- Development time สั้นที่สุด
- Prototype ก่อน แล้วค่อยตัดสินใจว่าจะ ship หรือเปลี่ยน technology

**Scope Phase 2:**
- Window หลักแสดงสถานะ containers (รัน `docker compose ps` และ parse output)
- ปุ่ม Start / Stop / Restart
- ปุ่มเปิดเบราว์เซอร์
- ปุ่ม View Logs
- Status indicator (สี) สำหรับแต่ละ container

**Bundle strategy:** ใช้ PyInstaller สร้าง single `.exe` — แนบเป็น optional component ใน Inno Setup installer

### Phase 3 (ระยะยาว ถ้า cross-platform จำเป็น): Tauri

- พิจารณาเมื่อต้องการรัน launcher บน Linux/macOS ด้วย
- ต้องการทีมที่มี Rust experience หรือยอมลงทุนเรียน
- ขนาด binary เล็กที่สุด เหมาะกับการ distribute แบบ offline

---

## ข้อสรุปและการตัดสินใจ

> **ณ วันที่ 2026-05-26:** ✅ **ตัดสินใจแล้ว — ใช้ Phase 2 (Python + CustomTkinter)**

**ผลลัพธ์ source-level:**
- `launcher/seamlessfordmis_launcher.py` — GUI Launcher source code
- `launcher/requirements.txt` — Python dependencies
- `launcher/build-launcher.bat` — build script (PyInstaller)
- `installer/seamlessfordmis.iss` — อัปเดตให้รวม Launcher EXE (optional, skipifsourcedoesntexist)

**สถานะ binary / verification:**
- `SeamlessFordMIS-Launcher.exe` ยังต้อง build บน Windows ด้วย `launcher\build-launcher.bat`
- Windows Clean VM verification ยัง pending — ห้าม claim production-ready จนกว่าจะมี test report จริง

**วิธี build:**
```bat
cd launcher
build-launcher.bat
```
Output: `launcher\SeamlessFordMIS-Launcher.exe` (~50-80 MB)

**วิธี build installer รวม launcher:**
```bat
installer\build-installer.bat
```
(build-installer.bat จะถามว่าต้องการ build launcher ก่อนหรือไม่)

**Fallback:** ถ้าไม่ build launcher EXE — installer ยังทำงานได้ปกติ โดยใช้ `control-panel.bat` เป็น shortcut หลัก

## สถานะล่าสุดสำหรับ build/installer

- GUI Launcher source-ready: `launcher/seamlessfordmis_launcher.py`
- GUI Launcher binary-built: `launcher/SeamlessFordMIS-Launcher.exe`
- Installer integration: `installer/seamlessfordmis.iss` include launcher ถ้ามี EXE และมี fallback เป็น `control-panel.bat`
- Build script: ใช้ `installer\build-installer.bat check`, `dev`, หรือ `offline-full`
- `offline-full` ต้องมี Docker image tarballs ครบใน `images\` ก่อน build installer
- Clean VM verification: pending — ห้าม claim production-ready จนกว่าจะมี test report จริง

---

**Phase 3 (Tauri) ยังเป็น long-term option** ถ้าในอนาคตต้องการ cross-platform (Linux/macOS) หรือขนาด binary เล็กลงมาก

---

*เอกสารนี้อัปเดตจาก proposal → implemented วันที่ 2026-05-26*
