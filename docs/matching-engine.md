# Matching Engine

เอกสารนี้สรุป matching engine หลัง Phase 4 และก่อน Phase 6 UX refinement

## Current Matching Rule

MVP matching ใช้:

```text
target_group_rows.normalized_cid == disease_screening_records.normalized_person_identifier
```

ไม่มี fuzzy matching

## Meaning Of Match Status

- `matched`
  - พบ identifier นี้ในฐานข้อมูลการตรวจโรค
- `not_found`
  - ไม่พบ identifier นี้ในฐานข้อมูลการตรวจโรค
- `needs_review`
  - แถว target group มีปัญหา เช่น invalid identifier
- `ambiguous`
  - ยังไม่ใช้เป็นเส้นทางหลักใน matching ปัจจุบัน

## Patient Master Linking

หลังพบ match ในฐานข้อมูลการตรวจโรคแล้ว ระบบจะพยายามผูก `patient_id` ถ้าพบใน `patients`

แต่การมีหรือไม่มี `patient_id` ไม่ได้เปลี่ยน fact หลักว่า:

- คนนี้พบในฐานข้อมูลการตรวจโรคหรือไม่

ดังนั้นในบางกรณี:

- `match_status = matched`
- แต่ `patient_id = null`

## Why This Matters For Result Generation

Phase 5 ต้องใช้ผลแบบนี้:

- มีประวัติใน selected services หรือไม่
- วันล่าสุดของ selected services

จึงต้องพึ่ง screening identifier match เป็นหลัก ไม่ใช่พึ่ง patient master link อย่างเดียว
