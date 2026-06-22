# Matching Rules

## Person Matching Precedence

1. `identifier_exact`
2. `name_exact_secondary`
3. `needs_review`
4. `not_found`

## Core Rules

- exact normalized identifier match เป็นกติกาหลักเสมอ
- secondary exact normalized full-name match ใช้เฉพาะเมื่อ identifier-based match หาไม่เจอ
- secondary name match ห้าม override exact identifier match
- ถ้าชื่อเดียวกันพาไปได้หลาย identity ต้องเป็น `needs_review`

## Matching Across Screening DB And Target Group File

### Disease Screening Database

- ใช้เป็น primary formal source สำหรับประวัติการตรวจโรค
- exact identifier match มาก่อน
- name-based fallback ใช้เฉพาะตามกติกาที่อนุมัติไว้

### Target Group File History

- ใช้เป็น secondary evidence source
- ใช้เมื่อ selected services ตรงกับประวัติใน sheet ประวัติของไฟล์กลุ่มเป้าหมาย
- ถ้า screening DB ไม่มีประวัติ แต่ target group file มีประวัติที่ผ่าน validation:
  - ห้ามจัดเป็น `ยังไม่เคยตรวจ`
  - ต้องจัดเป็น `target_group_file_only`

## Sheet Classification Rules

sheet ใน target group workbook ถูกจัดประเภทแบบ conservative:

- `target_group_roster`
- `target_group_screening_history`
- `target_group_other_context`
- `unknown_sheet_type`

ตัวช่วย classify:

- ชื่อ sheet
- ชื่อคอลัมน์
- การมี field เช่น `CID`, `ชื่อผู้ป่วย`, `วันที่ตรวจ`, `ICD10`, `HPV`, `ผลการตรวจ`, `สถานพยาบาล`, `ชื่อแพทย์`, `หมายเหตุ`

ถ้า sheet ยังไม่ชัด จะไม่ถูกเดาเป็น history อัตโนมัติ แต่จะถูก mark ให้ review

## Latest-date Rule

- latest date ต้องดูจาก selected services เท่านั้น
- รวม event จาก screening DB และ target group file history
- เลือก `MAX(date)` ของ event ที่เข้าเกณฑ์เท่านั้น
- ต้องเก็บ source provenance ของ latest event ไว้ด้วย

## Match Method Sent To UI

- `identifier_exact`
- `name_exact_secondary`
- `needs_review`
- `not_found`

## Traceability

result row และ history evidence ต้องเก็บหรือส่งต่อ:

- `match_method`
- `match_confidence`
- `matched_identifier`
- `matched_name_basis`
- `source_file_name`
- `source_sheet_name`
- `source_row_no`

เพื่อให้เจ้าหน้าที่เห็นได้ว่า evidence มาจากแหล่งไหน และใช้กติกาอะไรในการตัดสิน
