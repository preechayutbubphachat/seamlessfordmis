# Hospital Group Treatment History Filter

## วัตถุประสงค์

ระบบเว็บภายในสำหรับเจ้าหน้าที่โรงพยาบาลเพื่อ:
- sync ข้อมูลประวัติการรักษาจากไฟล์ Excel ใน `data/`
- ตรวจว่าข้อมูลต้นทางเปลี่ยนหรือไม่ก่อนเปิดระบบ
- อัปโหลดรายชื่อผู้ป่วยเป็นกลุ่ม
- จับคู่กลุ่มผู้ป่วยกับฐานข้อมูลหลัก
- ค้นและกรองประวัติการรักษาตามโรคหรือบริการ
- แสดงวันที่ล่าสุด จำนวนครั้ง และช่วงเวลาที่ผ่านไป
- export ผลลัพธ์ออก Excel/CSV

## หลักการสำคัญ

- import ต้องปลอดภัยด้วย staging + transaction + rollback
- ต้อง trace กลับได้ว่าแต่ละผลลัพธ์มาจาก import ไหนและไฟล์ไหน
- ห้ามเดาข้อมูลที่ไม่มี
- missing data ต้องไม่ตีความว่าไม่เคยมีโรค
- ออกแบบให้รองรับ PDF parser ในเฟสถัดไป

## ขอบเขต MVP

- import ฐานหลักจาก Excel
- ตรวจ hash ไฟล์ก่อน sync
- upload กลุ่มเป้าหมายจาก Excel
- match ด้วย `PID -> citizen ID -> HN -> name + birth date`
- name-only ต้อง flag `needs_review`
- filter ตามโรค, diagnosis code, หรือ normalized disease key
- dashboard สถานะระบบ
- export CSV/Excel
- audit log ขั้นพื้นฐาน

## เฟสถัดไป

- PDF text-based import
- OCR review flow
- manual review UI สำหรับ ambiguous match
- disease mapping UI
- RBAC และ background jobs เต็มรูปแบบ
