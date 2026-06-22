# Production Safety

เอกสารนี้สรุปสิ่งที่ระบบรับประกันได้แล้วหลัง Phase 9 และสิ่งที่ยังเป็นข้อจำกัดที่ต้องระวัง

## สิ่งที่ระบบรับประกันได้ตอนนี้

- disease screening import เป็น staging-first
- merge เข้า production ทำผ่าน service กลางและไม่เอา invalid rows เข้าโดยเงียบ ๆ
- target group import เก็บ provenance ระดับไฟล์และระดับแถว
- matching, result generation, export มี audit event แบบ `started/success/failed/reused`
- dashboard และ target group pages มี safe error state แทนการ crash ทั้งหน้า
- export ใช้ result logic ชุดเดียวกับ UI

## Idempotency / Rerun Safety

### Disease Screening Import

- idempotent ระดับ `source_set_hash`
- ถ้าชุดไฟล์ต้นทางเหมือนงานล่าสุดที่สำเร็จ ระบบจะ reuse summary เดิม
- ถ้าชุดไฟล์เปลี่ยน จะสร้าง import job ใหม่

### Target Group Import

- partial-safe
- ป้องกันไฟล์ซ้ำใน upload request เดียวกันจาก `sha256`
- upload ซ้ำคนละ job ยังอนุญาตเพื่อคง audit trail

### Matching

- partial-safe
- rerun group เดิมจะเขียนทับ `match_status` ของ target rows ใน group นั้น
- ไม่มี fuzzy fallback แอบทำงาน

### Result Generation

- idempotent ระดับ `selected_service_hash`
- ถ้า result set ล่าสุดของ group ใช้ selection เดียวกัน ระบบจะ reuse ได้
- ถ้า selection เปลี่ยน จะลบผลเดิมของ group แล้วสร้างชุดใหม่

### Export

- idempotent เชิง business context
- export ซ้ำทำได้
- ถ้า selection ปัจจุบันไม่ตรงกับ result set ล่าสุด ระบบจะ fail ชัดเจน

## Recovery Steps

### Frontend Next.js missing chunk

ใน `frontend/`

```bash
npm run dev:clean
```

### Backend migration mismatch

ใน `backend/`

```bash
python -m alembic upgrade head
```

### ตรวจ backend health

- `GET /health`
- `GET /api/system/status`

## Operational Guidance

- sync ฐานข้อมูลการตรวจโรคก่อนใช้งานผลลัพธ์จริง
- หลัง upload target group ให้ดู validation summary ก่อนจับคู่
- หลังเปลี่ยน selected services ต้องสร้างผลลัพธ์ใหม่ก่อน export
- ถ้าพบ `warning` หรือ `needs_review` ให้ตรวจ file provenance และ row context ก่อนใช้งานเชิงปฏิบัติการ
