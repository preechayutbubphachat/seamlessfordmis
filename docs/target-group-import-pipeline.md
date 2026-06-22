# Target Group Import Pipeline

เอกสารนี้สรุป Phase 3 ของการนำเข้ากลุ่มเป้าหมาย โดยเป้าหมายคือเตรียมข้อมูลให้พร้อมสำหรับการ match ใน Phase 4 แบบปลอดภัยและ trace ได้

## ขอบเขตของ Phase 3

Phase 3 ครอบคลุม:

- สร้าง target group job หนึ่งงาน
- รับหลายไฟล์ในงานเดียวกัน
- parse ข้อมูลจาก Excel/CSV
- เก็บ placeholder path สำหรับ PDF ไว้ก่อน
- เก็บ raw values และ provenance ต่อแถว
- normalize CID และข้อมูลประกอบที่สำคัญ
- validate ต่อแถว
- สรุปภาพรวม import สำหรับ preview หน้าเว็บ

Phase 3 ยังไม่ครอบคลุม:

- final matching กับฐานข้อมูลการตรวจโรค
- fuzzy matching
- final results/reporting เชิงธุรกิจ

## โครงสร้างข้อมูลหลัก

### target_group_jobs

ใช้แทน logical batch เดียวของกลุ่มเป้าหมาย

เก็บอย่างน้อย:

- ชื่อกลุ่ม
- จำนวนไฟล์
- source set hash
- parse status
- match status
- summary counters เช่น valid/invalid/duplicate CID

### target_group_job_files

แทนแต่ละไฟล์ที่อัปโหลดใน job เดียวกัน

เก็บ:

- file name
- file path
- file type
- sha256
- file size
- uploaded/provenance metadata
- parse status
- row count
- warning count
- parse error summary

### target_group_rows

เป็น staging row level

เก็บ:

- provenance (`group_job_id`, `source_file_id`, `source_file_name`, `source_row_no`)
- raw fields (`raw_cid`, `raw_full_name`, `raw_age`, `raw_sex`, `raw_json`)
- normalized fields (`normalized_cid`, `normalized_full_name`, `normalized_age`, `normalized_sex`)
- statuses (`parse_status`, `validation_status`, `cid_validation_status`, `duplicate_status`)
- `error_message`, `warning_message`

## Import Flow

1. ผู้ใช้สร้างหนึ่ง target group job ผ่านชื่อกลุ่ม + หลายไฟล์
2. ระบบบันทึกไฟล์ลง storage ชั่วคราว
3. ระบบ fingerprint ไฟล์ทุกไฟล์และสร้าง source set hash
4. สร้าง `target_group_job_files` ต่อไฟล์
5. เลือก importer ตามชนิดไฟล์
6. parse แถวเป็น staging rows
7. normalize CID, ชื่อ, อายุ, เพศ
8. validate ต่อแถว
9. ตรวจ CID ซ้ำภายใน job
10. สรุป import summary ระดับ job และระดับไฟล์

## ชนิดไฟล์ที่รองรับ

รองรับเต็มใน Phase 3:

- `.xlsx`
- `.xls`
- `.csv`

รองรับแบบ staged-safe:

- `.pdf`

หมายเหตุ:

- PDF ยังไม่ใช่เส้นทางหลักใน Phase 3
- scanned PDF ยังต้องพึ่ง manual review ใน phase ถัดไป

## Duplicate CID Rules

- ตรวจภายใน job เดียว
- CID ซ้ำไม่ถูกลบทิ้ง
- ทุกแถวที่ CID ซ้ำจะถูก mark เป็น `duplicate_in_job`
- ถ้าแถวนั้นเดิมเป็น `valid` จะถูกยกระดับเป็น `warning`
- summary ของ job ต้องรายงานจำนวนแถว CID ซ้ำ

## Summary ที่ต้องได้หลัง import

- total uploaded files
- total rows
- parsed rows
- valid CID rows
- invalid CID rows
- missing CID rows
- duplicate CID rows
- warning rows
- failed rows

## API ที่ใช้ใน Phase 3

- `POST /api/target-groups/upload-files`
- `GET /api/target-groups/{group_id}`
- `GET /api/target-groups/{group_id}/files`
- `GET /api/target-groups/{group_id}/validation-summary`

## Known Limitations

- ยังไม่ทำ final matching
- ยังไม่ dedupe CID ซ้ำเชิงธุรกิจ
- PDF scanned ยังเป็น TODO
- preview ยังเป็นแค่ตัวอย่างแถวแรก ไม่ใช่ full review UI

## TODO สำหรับ Phase 4

- deterministic matching ด้วย `normalized_person_identifier == normalized_cid`
- แยกสถานะ `matched / not_found / ambiguous / needs_review` ให้ชัด
- นำ import summary และ validation summary ไปใช้กับ workflow หน้าเว็บแบบเต็ม
