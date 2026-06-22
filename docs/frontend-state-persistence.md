# Frontend State Persistence

## วิธีที่ใช้

ใช้ URL query params เป็นหลัก เพื่อให้:

- refresh แล้วค่าหลักยังอยู่
- share URL แล้วบริบทการกรองยังอยู่

## Query Params

- `services`
  - comma-separated selected service keys
- `view`
  - current result filter
- `overdue`
  - overdue threshold in years
- `q`
  - text search

## ค่าเริ่มต้น

- selected services
  - ใช้รายการแรกจาก disease options ถ้ายังไม่มีใน URL
- overdue threshold
  - `1` ปี
- view
  - `all`

## ข้อควรระวัง

- ถ้า selected services ใน URL ไม่ตรงกับ result set ล่าสุด ระบบยังแสดงผลล่าสุดได้ แต่จะเตือนให้สร้างผลใหม่ก่อน export
