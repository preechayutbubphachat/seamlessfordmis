# Field Mapping

เอกสารนี้สรุป field mapping ปัจจุบันของระบบ โดยยึดแนวคิดว่า raw source ต้องถูกเก็บไว้ก่อนเสมอ และการ normalize ต้องทำแบบตรวจสอบย้อนหลังได้

## หลักการร่วม

- ห้ามเดาค่าที่ไม่มี
- raw source ต้องถูกเก็บไว้ก่อน normalize
- staging ต้องเก็บ provenance กลับไปถึงไฟล์และแถวต้นทางได้
- field alias เก่าอาจยังอยู่ชั่วคราวเพื่อ compatibility แต่ flow ใหม่ต้องยึด field หลักตามเอกสารนี้

## ฐานข้อมูลการตรวจโรค

คอลัมน์ `VCTID,NAPNumber,PID` ต้องถูกตีความเป็น identifier เดียว ไม่แยกเป็น 3 ช่อง

### Field หลัก

- `VCTID,NAPNumber,PID` -> `raw_person_identifier`
- `raw_person_identifier` -> `normalized_person_identifier`
- `ชื่อ-สกุล` หรือ field ชื่อที่เทียบเท่า -> `raw_full_name`
- `raw_full_name` -> `normalized_full_name`
- `รายการที่ขอเบิก` / `service_item_name` / field ที่เทียบเท่า -> `raw_service_type`
- `raw_service_type` -> `normalized_service_key`
- `วันที่รับบริการ` / `visit_date` / field ที่เทียบเท่า -> `raw_visit_date`
- `raw_visit_date` -> `normalized_visit_date`
- `hcode` -> `raw_hcode`
- `transaction_id` -> `raw_transaction_id`
- `rep_no` -> `raw_rep_no`

### Provenance

ทุกแถวต้องเก็บ:

- `source_file_id`
- `source_file_name`
- `source_row_no`
- `raw_json`

## กลุ่มเป้าหมาย

ในไฟล์กลุ่มเป้าหมาย field หลักของ MVP คือ `CID`

### Field หลัก

- `CID` -> `raw_cid`
- `raw_cid` -> `normalized_cid`
- `ชื่อผู้ป่วย` / `full_name` -> `raw_full_name`
- `raw_full_name` -> `normalized_full_name`
- `อายุ` / `age_text` -> `raw_age`
- `raw_age` -> `normalized_age`
- `เพศ` / `sex` -> `raw_sex`
- `raw_sex` -> `normalized_sex`

### Provenance

ทุกแถวต้องเก็บ:

- `group_job_id`
- `source_file_id`
- `source_file_name`
- `source_row_no`
- `raw_json`

## หมายเหตุด้าน compatibility

- field อย่าง `normalized_pid`, `normalized_citizen_id`, `normalized_hn` ยังอาจถูกเติมไว้ในบาง flow เพื่อไม่ให้ของเดิมพังทันที
- Phase 4 ควรเริ่มย้าย matching logic ไปใช้ `normalized_person_identifier == normalized_cid` โดยตรง

## ประเด็นที่ยังต้องตรวจข้อมูลจริงเพิ่ม

- มีไฟล์ใดบ้างที่ `VCTID,NAPNumber,PID` ไม่ใช่เลข 13 หลักหรือมีรูปแบบพิเศษ
- policy สำหรับ `CID` ซ้ำภายใน target group job ควรถูก dedupe หรือให้คงทุกแถวไว้เพื่อ review
- field ชื่อ/เพศ/อายุ ในแต่ละหน่วยงานใช้ชื่อคอลัมน์ต่างกันแค่ไหน
