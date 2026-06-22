# Validation Rules

เอกสารนี้สรุปกติกา validation ที่ใช้กับการนำเข้า การจับคู่ การสร้างผลลัพธ์ และการ export หลัง Phase 9

## หลักการ

- ห้ามเดาข้อมูลที่หาย
- ต้องเก็บ raw source values ไว้ก่อน normalize เสมอ
- invalid และ missing data ต้องยังมองเห็นได้
- staging ต้องแยกจาก production merge
- latest-date calculation ใช้เฉพาะบริการที่ผู้ใช้เลือก

## Disease Screening Import

### Identifier

- `valid_identifier`
- `invalid_identifier`
- `missing_identifier`

กติกา:

- `raw_person_identifier` ต้องถูกเก็บเสมอ
- `normalized_person_identifier` ต้องผ่านกติกา identifier จึงจะ merge เข้า production ได้
- แถวที่ identifier ไม่ผ่านเกณฑ์ยังอยู่ใน staging แต่ไม่ merge

### Date

- `valid_date`
- `invalid_date`
- `missing_date`

กติกา:

- `normalized_visit_date` ที่ไม่ผ่านเกณฑ์ต้องไม่ถูกใช้ในการคำนวณวันที่ล่าสุด
- invalid หรือ missing date ทำให้แถวนั้นไม่เข้าสู่ production result logic

### Service

- `known_service`
- `unknown_service`
- `missing_service`

กติกา:

- `missing_service` ต้องแสดงชัด ไม่ถูกตีความว่าไม่มีประวัติ
- `unknown_service` อยู่ใน warning scope ได้ แต่ยังต้อง trace กลับไปถึง source row

## Target Group Import

### CID

- `valid_identifier`
- `invalid_identifier`
- `missing_identifier`

กติกา:

- `raw_cid` ต้องถูกเก็บเสมอ
- `normalized_cid` ห้ามเดาเมื่อ normalize ไม่ได้
- แถว CID ผิดหรือหายยังอยู่ใน staging

### Duplicate Status

- `unique_in_job`
- `duplicate_in_job`

กติกา:

- ตรวจ duplicate ภายใน target group job เดียว
- duplicate ไม่ถูกลบทิ้งเงียบ ๆ
- duplicate ต้องถูก mark เป็น `warning`

## Result Generation

### Result Categories

- `has_selected_history`
- `no_selected_history`
- `invalid_identifier`
- `missing_identifier`
- `needs_review`

กติกา:

- `invalid_identifier` และ `missing_identifier` ไม่ใช่ `no_selected_history`
- `no_selected_history` ใช้เฉพาะ valid identifier ที่ไม่พบ selected services
- `needs_review` ใช้เมื่อ matching flow มีเหตุผลจริงเท่านั้น

### Summary Formula

- `total_target_people` = จำนวน target rows ทั้งหมดในชุดผลลัพธ์
- `invalid_identifier_people` = จำนวนแถวที่เป็น `invalid_identifier` หรือ `missing_identifier`
- `valid_identifier_people` = `total_target_people - invalid_identifier_people`
- `people_with_selected_history` = จำนวน valid rows ที่พบ selected services
- `people_without_selected_history` = จำนวน valid rows ที่ไม่พบ selected services

ต้องเป็นจริงเสมอ:

```text
people_with_selected_history + people_without_selected_history = valid_identifier_people
```

Coverage:

```text
coverage_percent = (people_with_selected_history / valid_identifier_people) * 100
```

ถ้า `valid_identifier_people = 0` ให้ `coverage_percent = 0`

## Export Validation

กติกา:

- export ต้องใช้ selected service context เดียวกับผลลัพธ์ล่าสุด
- ถ้า selection ปัจจุบันไม่ตรงกับ result set ล่าสุด ให้ fail ชัดเจน
- export ต้องไม่คำนวณ summary หรือ person rows ใหม่ด้วยสูตรคนละชุด

## Rerun / Idempotency Notes

- disease screening import:
  - ถ้า `source_set_hash` ไม่เปลี่ยนและงานล่าสุดสำเร็จ ระบบ reuse summary เดิม
- target group import:
  - ป้องกันไฟล์ซ้ำภายใน upload request เดียว
  - การ upload ซ้ำคนละ job ยังอนุญาต แต่แยก provenance ชัดเจน
- matching:
  - rerun จะอัปเดต match status ชุดเดิมของ group เดิม
- result generation:
  - ถ้า `selected_service_hash` เดิมและผลลัพธ์ล่าสุดยังอยู่ ระบบ reuse ได้
- export:
  - rerun ได้ แต่ต้องอยู่บน result context เดียวกัน

## Known Limitations

- scanned PDF ยังเป็น staged-safe placeholder
- target group upload ซ้ำต่าง job ยังไม่ dedupe ข้าม job
- result set ยังเก็บเป็น latest snapshot ของแต่ละ group เป็นหลัก
