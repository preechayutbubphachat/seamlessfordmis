# Result Generation

เอกสารนี้อธิบายกติกา Phase 5 และ Phase 6 ของการสร้างผลลัพธ์จากกลุ่มเป้าหมาย โดยยึดหลักว่า `last_visit_date` ต้องคำนวณจากเฉพาะ service ที่ผู้ใช้เลือกเท่านั้น

## Input

- target group job หนึ่งงาน
- selected service keys ตั้งแต่ 1 ค่า

ถ้าไม่เลือก service เลย ระบบจะ reject ด้วย validation error ชัดเจน

## Source Of Truth

1. ใช้ `target_group_rows.normalized_cid` เป็นตัวแทนคนในกลุ่มเป้าหมาย
2. ใช้ `disease_screening_records.normalized_person_identifier` เป็นตัวแทนคนในฐานข้อมูลการตรวจโรค
3. ใช้กติกา match แบบ:
   - `normalized_person_identifier == normalized_cid`
4. ใช้เฉพาะ `disease_screening_records.normalized_service_key` ที่อยู่ใน selected service keys หลังผ่าน alias expansion

## Person-level Logic

สำหรับแต่ละ target row:

1. ถ้า identifier หาย:
   - `result_category = missing_identifier`
   - `has_selected_service = false`
   - `matching_record_count = 0`
2. ถ้า identifier ไม่ถูกต้อง:
   - `result_category = invalid_identifier`
   - `has_selected_service = false`
   - `matching_record_count = 0`
3. ถ้า identifier ใช้ได้:
   - หา disease screening records ที่ identifier ตรงกัน
   - filter ด้วย selected service keys
   - คำนวณ:
     - `matching_record_count`
     - `matched_service_keys`
     - `last_visit_date`
     - `days_since_last_visit`
     - `years_since_last_visit`
4. ถ้าพบอย่างน้อยหนึ่ง record ใน selected services:
   - `result_category = has_selected_history`
5. ถ้าไม่พบ record ใน selected services:
   - `result_category = no_selected_history`
6. ถ้า matching flow ก่อนหน้า mark แถวนั้นเป็น review case จริง:
   - `result_category = needs_review`

## Latest Date Rule

`last_visit_date` ต้องเป็น:

- `MAX(visit_date)` จาก record ที่ผ่านการ filter ด้วย selected service keys แล้วเท่านั้น

ห้ามใช้ record ของ service อื่นมาปน

## Summary Formulas

- `total_target_people = จำนวน target rows ทั้งหมดในผลลัพธ์`
- `valid_identifier_people = จำนวนแถวที่ identifier ใช้งานได้`
- `invalid_identifier_people = จำนวนแถวที่เป็น invalid_identifier หรือ missing_identifier`
- `people_with_selected_history = จำนวนแถวที่ result_category = has_selected_history`
- `people_without_selected_history = จำนวนแถวใน valid scope ที่ไม่มี selected-service history`

ดังนั้น:

```text
people_with_selected_history + people_without_selected_history = valid_identifier_people
```

## Coverage Formula

Phase 6 ล็อกให้ใช้ตัวหารเป็น `valid_identifier_people`

```text
coverage_percent = (people_with_selected_history / valid_identifier_people) * 100
```

ถ้า `valid_identifier_people = 0` ให้ `coverage_percent = 0`

## Storage Strategy

แนวทางปัจจุบันเป็นแบบ conservative:

- ลบผลลัพธ์เก่าของ group เดิมก่อนสร้างใหม่
- เก็บผลล่าสุดไว้ใน `target_group_results`
- หนึ่งแถวผลลัพธ์แทนหนึ่ง target row ของ selection set ล่าสุด

## Optional Breakdown

ระบบสามารถส่ง per-service breakdown ได้:

- `selected_service_key`
- `distinct_people_count`
- `matching_record_count`

โดย priority หลักยังเป็น:

1. group summary
2. person-level result rows

## Known Limitations

- duplicate CID ยังนับตาม target rows ไม่ได้ dedupe เป็น logical person เต็มรูปแบบ
- selected result set ยังเก็บเป็นผลล่าสุดของ group เดียว ไม่ใช่หลาย snapshot พร้อมกัน
- `needs_review` ยังขึ้นกับ matching flow ก่อนหน้า ไม่ใช่ manual review workflow เต็มรูปแบบ
