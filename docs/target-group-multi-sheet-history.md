# Target Group Multi-Sheet History

## Purpose

target group Excel อาจมีมากกว่า 1 sheet และบาง sheet มีประวัติการตรวจ/รักษาอยู่แล้ว

รอบนี้ระบบจึงต้อง:

- อ่านทุก sheet
- จัดประเภทแต่ละ sheet อย่าง conservative
- เก็บประวัติจาก target group file เป็น secondary evidence source
- ไม่ปล่อยให้คนที่มีประวัติในไฟล์ถูกจัดเป็น `ยังไม่เคยตรวจ`

## Sheet Types

- `target_group_roster`
  - ใช้สร้าง `target_group_rows`
  - เป็นชุดสมาชิกกลุ่มเป้าหมายสำหรับ matching/reporting

- `target_group_screening_history`
  - ใช้สร้าง `target_group_history_rows`
  - เป็น event/history source จากไฟล์กลุ่มเป้าหมาย

- `target_group_other_context`
  - ยังไม่ใช้ใน result generation รอบนี้
  - ถูก mark เป็น context sheet

- `unknown_sheet_type`
  - ยังจัดประเภทไม่ได้
  - ถูก mark ให้ตรวจสอบ

## Classification Logic

ใช้ข้อมูลต่อไปนี้ร่วมกัน:

- ชื่อ sheet
- ชื่อคอลัมน์
- การมี field เช่น:
  - `CID`
  - `ชื่อผู้ป่วย`
  - `ชื่อ-สกุล`
  - `วันที่ตรวจ`
  - `ICD10`
  - `HPV`
  - `ผลการตรวจ`
  - `สถานพยาบาล`
  - `ชื่อแพทย์`
  - `หมายเหตุ`

กติกาโดยย่อ:

- ถ้ามี person columns + history columns ให้จัดเป็น `target_group_screening_history`
- ถ้ามี person columns + roster columns ให้จัดเป็น `target_group_roster`
- ถ้า hint ยังไม่พอ จะไม่ถูกเดาเป็น history ทันที แต่จะถูก mark review

## New Table

ใช้ตาราง `target_group_history_rows` สำหรับเก็บ history event จากไฟล์กลุ่มเป้าหมาย

field สำคัญ:

- `group_job_id`
- `source_file_id`
- `source_file_name`
- `source_sheet_name`
- `source_row_no`
- `raw_cid`
- `normalized_cid`
- `raw_full_name`
- `normalized_full_name`
- `raw_service_type`
- `normalized_service_key`
- `raw_visit_date`
- `normalized_visit_date`
- `raw_icd10`
- `raw_result`
- `raw_hpv`
- `raw_hospital`
- `raw_doctor`
- `raw_note`
- `parse_status`
- `validation_status`
- `identifier_validation_status`
- `date_validation_status`
- `service_validation_status`
- `warning_message`
- `raw_json`

## Source Precedence In Result Generation

1. screening DB history มาก่อน
2. ถ้า screening DB ไม่พบ แต่ target group file history พบ ให้ใช้ target group file history
3. ถ้าไม่พบทั้งสองแหล่ง จึงจัดเป็น `no_history_found`

## Important Business Rule

ถ้ามีประวัติใน sheet ประวัติของไฟล์กลุ่มเป้าหมาย:

- ห้ามจัดเป็น `ยังไม่เคยตรวจ`
- ต้องแยกให้เห็นว่า evidence มาจาก `target_group_file_only` หรือ `both_sources`

## Known Limitations

- sheet ที่กำกวมยังไม่ถูกตีความอัตโนมัติ
- event extraction ของ target group history ยังเป็น conservative mapping
- ถ้า 1 แถวมีหลายผลตรวจ ระบบจะใช้ key แบบรวมเพื่อหลีกเลี่ยงการเดาผิด
