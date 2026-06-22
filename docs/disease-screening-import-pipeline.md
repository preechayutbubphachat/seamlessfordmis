# Disease Screening Import Pipeline

เอกสารนี้อธิบาย Phase 2 ของการนำเข้า `ฐานข้อมูลการตรวจโรค` โดยเน้นความถูกต้อง ความสามารถในการ audit และการเก็บ staging ก่อน merge เข้าฐาน production

## Source file expectations

- รองรับไฟล์ `.xlsx`, `.xls`, `.csv` แบบทำงานจริง
- `.pdf` ยังเป็น staged-safe path
  - text-based PDF: เก็บ raw extracted text และ mark ว่า parse failed / needs review
  - scanned PDF: ยังไม่สร้าง structured rows อัตโนมัติ
- คอลัมน์ `VCTID,NAPNumber,PID` ถูกตีความเป็น identifier เดียว

## Import flow

1. ค้นหาไฟล์ต้นทางจากโฟลเดอร์ที่ตั้งค่าไว้
2. เก็บ metadata ต่อไฟล์:
   - file name
   - file path
   - file type
   - size
   - sha256
   - modified time
   - discovered time
3. parse แต่ละแถวเข้า `staging_history_records`
4. normalize fields สำคัญ:
   - `raw_person_identifier` -> `normalized_person_identifier`
   - `raw_service_type` -> `normalized_service_key`
   - `raw_visit_date` -> `normalized_visit_date`
5. validate ต่อแถว
6. persist summary ระดับไฟล์และระดับ import job
7. merge เฉพาะแถวที่ผ่านเกณฑ์เข้า production

## Staging fields

ฟิลด์สำคัญใน staging:

- provenance
  - `import_job_id`
  - `source_file_id`
  - `source_file_name`
  - `source_row_no`
- raw values
  - `raw_person_identifier`
  - `raw_full_name`
  - `raw_service_type`
  - `raw_visit_date`
  - `raw_hcode`
  - `raw_transaction_id`
  - `raw_rep_no`
  - `raw_json`
- normalized values
  - `normalized_person_identifier`
  - `normalized_full_name`
  - `normalized_service_key`
  - `normalized_visit_date`
- statuses
  - `parse_status`
  - `validation_status`
  - `identifier_validation_status`
  - `date_validation_status`
  - `service_validation_status`
  - `error_message`
  - `warning_message`

## Merge rules

- merge อยู่ใน transaction เดียวกับการเขียน production snapshot
- merge เฉพาะแถวที่:
  - parse สำเร็จ
  - identifier ใช้งานได้
  - service type มีค่าและ normalize ได้
  - visit date parse ได้
- invalid rows ยังคงอยู่ใน staging เพื่อ review ภายหลัง
- ป้องกัน duplicate ขั้นต่ำโดย dedupe จาก `(import_job_id, source_file_id, source_row_no)`

## Production model

ใช้ table `disease_screening_records` สำหรับข้อมูลที่พร้อมใช้ downstream:

- `raw_person_identifier`
- `normalized_person_identifier`
- `full_name`
- `normalized_full_name`
- `raw_service_type`
- `normalized_service_key`
- `visit_date`
- `hcode`
- `transaction_id`
- `rep_no`
- `source_import_job_id`
- `source_file_id`
- `source_row_no`

## Known limitations

- current merge strategy เป็น snapshot replace ทั้งชุด ยังไม่ใช่ incremental upsert
- duplicate identifier ระหว่างหลาย visit ยังถูกเก็บไว้ตามจริง ต้อง aggregate ใน phase report ภายหลัง
- PDF parsing ยังเป็น TODO แบบปลอดภัย ไม่ใช่ structured import เต็มรูปแบบ
