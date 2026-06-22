# Loading and Progress UX

## เป้าหมาย

ระบบต้องสื่อให้ผู้ใช้เข้าใจได้ทันทีว่า:

- กำลังโหลดหน้าอยู่
- กำลังประมวลผลงานที่ใช้เวลา
- งานเสร็จแล้ว
- งานล้มเหลวและควรทำอะไรต่อ

## สิ่งที่เพิ่มในรอบนี้

- เพิ่ม route-level loading ผ่าน `loading.tsx` สำหรับ:
  - หน้า dashboard
  - หน้ากลุ่มเป้าหมาย
  - หน้ารายละเอียดกลุ่มเป้าหมาย
- เพิ่ม reusable components:
  - `LoadingState`
  - `PageLoadingSkeleton`
  - `JobProgressCard`
  - `RetryErrorState`
- ปรับ action ที่ใช้เวลานานให้มี processing state ชัดเจน:
  - sync disease screening database
  - upload target group files
  - generate results
  - refresh results
  - run match
  - export

## หลักการแสดง progress

- ถ้า backend มีเพียงสถานะขั้นตอน ให้ใช้ stage-based progress
- ถ้า backend มีจำนวน processed/total ที่เชื่อถือได้ จึงค่อยแสดงตัวเลขประกอบ
- ห้ามสร้างเปอร์เซ็นต์ปลอมเพื่อให้ดูเหมือนระบบทำงานละเอียดกว่าความจริง

## จุดที่ใช้ true progress vs stage-based progress

### ใช้ stage-based progress

- dashboard sync
- target group upload
- target group matching
- result generation
- export preparation

เหตุผล:

- backend ยังไม่ได้เปิด endpoint สำหรับ live progress แบบ row-by-row
- งานส่วนใหญ่ยังตอบกลับเมื่อเสร็จสิ้นในคำขอเดียว

### ใช้ processed/total เมื่อมีหลังจบงาน

- target group upload summary
- disease screening sync summary

หมายเหตุ:

- ค่านี้ใช้สรุปผลหลังงานจบ ไม่ใช่ live progress ระหว่างรอ

## รูปแบบข้อความไทยที่ใช้

- โปรดรอสักครู่...
- กำลังโหลดข้อมูล...
- กำลังนำเข้าข้อมูล...
- กำลังจับคู่ข้อมูล...
- กำลังสร้างผลลัพธ์...
- กำลังเตรียมไฟล์รายงาน...
- เสร็จสิ้น
- ไม่สำเร็จ
- พบข้อผิดพลาด
- กรุณาลองใหม่อีกครั้ง

## ข้อจำกัดปัจจุบัน

- ยังไม่มี polling job progress จาก backend แบบเต็มรูปแบบ
- progress ของงานยาวหลายจุดจึงยังเป็น stage-based
- หากต้องการ live percentage จริง ควรเพิ่ม job status endpoint แยกใน backend รอบถัดไป
