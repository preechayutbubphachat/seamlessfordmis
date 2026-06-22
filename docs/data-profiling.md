# Data Profiling

Phase 0 เพิ่ม profiling mechanism เพื่อดูคุณภาพข้อมูลจริงก่อน refactor matching/reporting รอบใหญ่

## Outputs

profiling scripts จะสร้าง output ที่ `backend/reports/`

- `disease_screening_profile.json`
- `disease_screening_profile.md`
- `target_group_profile.json`
- `target_group_profile.md`

## Disease screening profiling checks

สำหรับไฟล์ฐานข้อมูลการตรวจโรค profiling จะสรุป:

- available columns
- row count
- non-null count ของคอลัมน์สำคัญ
- sample ค่าใน service column
- parseability ของ date columns
- คุณภาพของ `VCTID,NAPNumber,PID`
- สัดส่วนที่ดูเหมือนเลข 13 หลัก
- duplicate rate ของ normalized identifier
- null / invalid rate

## Target group profiling checks

สำหรับไฟล์กลุ่มเป้าหมาย profiling จะสรุป:

- available columns
- row count
- non-null count ของคอลัมน์สำคัญ
- คุณภาพของ `CID`
- duplicate rate ของ normalized CID
- null / invalid rate

## Why profiling comes before matching changes

การเปลี่ยน matching algorithm โดยไม่ profile ข้อมูลจริงก่อนมีความเสี่ยงสูง เพราะ:

- อาจใช้ field ผิด
- อาจ normalize ไม่พอหรือมากเกินไป
- อาจตีความข้อมูล missing เป็นข้อมูลลบโดยไม่ตั้งใจ
- อาจทำให้ latest-date/reporting ใน phase ถัดไปผิดทั้งระบบ

## Current phase boundary

Phase นี้ตั้งใจให้ได้:

- profiling ที่รันซ้ำได้
- report ที่ทีมข้อมูลอ่านได้
- anomaly list
- unresolved questions สำหรับปิดกับเจ้าของข้อมูลก่อน phase 2
