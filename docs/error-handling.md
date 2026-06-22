# Error Handling

## Backend

ระบบ backend ส่ง structured error response แทน `backend_error {}` แบบเดิม

หลักการ:

- ใช้ HTTP status code ให้ตรงสถานการณ์
- ส่งข้อความที่อธิบายเชิงปฏิบัติการได้
- ไม่ใส่ row-level PHI ลงใน error response
- เก็บรายละเอียดเพิ่มเติมไว้ใน audit log และ server log

สถานการณ์หลัก:

- `400` เมื่อ input ไม่ครบหรือ selection ไม่ถูกต้อง
- `404` เมื่อไม่พบ group/job ที่ร้องขอ
- `500` เฉพาะกรณี exception ที่ไม่คาดคิด

## Frontend

หน้า UI ต้องแยกสถานะต่อไปนี้ให้ผู้ใช้เห็นชัด:

- กำลังโหลด
- ยังไม่มีข้อมูล
- validation ไม่ผ่าน
- backend error
- operational warning

กติกา:

- API ตัวเดียวล้มต้องไม่ทำให้ทั้งหน้า crash
- ถ้ามีรายละเอียดจาก backend ให้แสดงข้อความนั้น
- ถ้าไม่มี payload ให้แสดง fallback พร้อม status code

## Import / Match / Result / Export Failures

- import failure:
  - ต้อง mark job เป็น `failed`
  - ต้องมี audit event พร้อม `error_summary`
- matching failure:
  - ต้อง mark `match_status = failed`
- result generation failure:
  - ต้องมี audit event `failed`
- export failure:
  - ต้อง fail ชัดเมื่อ result context ไม่ตรงกับ selection
