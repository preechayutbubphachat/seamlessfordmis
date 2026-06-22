# Normalization Rules

เอกสารนี้อธิบายกติกา normalize ที่ใช้ใน Phase 1

## Identifier normalization

ฟังก์ชัน: `normalize_identifier(value)`

กติกา:

1. แปลงค่าเป็น text แบบปลอดภัย
2. trim ช่องว่างหัวท้าย
3. normalize unicode ด้วย `NFKC`
4. collapse whitespace ซ้ำ
5. ลบ separator ที่ปลอดภัย:
   - space
   - hyphen (`-`)
6. ถ้าพบรูปแบบ Excel เช่น `1234567890123.0` ให้ลบ `.0`
7. ไม่เดา field ที่หาย
8. เก็บ raw value แยกจาก normalized value เสมอ

### Identifier validity

- `valid_identifier`:
  - หลัง normalize แล้วเป็นเลข 13 หลักพอดี
- `invalid_identifier`:
  - มีค่า แต่หลัง normalize แล้วไม่เป็นเลข 13 หลัก
- `missing_identifier`:
  - ไม่มีค่าหรือเหลือว่างหลัง normalize

หมายเหตุ:
- phase นี้ intentionally เข้มงวด เพื่อให้เห็นปัญหาข้อมูลจริงก่อน
- ถ้าภายหลังยืนยันได้ว่ามี format อื่นที่ถูกต้อง ต้องแก้กติกาพร้อมหลักฐานจาก profiling

## Name normalization

ฟังก์ชัน: `normalize_name(value)`

กติกา:

- trim
- normalize unicode
- collapse whitespace
- casefold

Phase นี้ยังไม่ใช้ fuzzy matching จากชื่อ

## Service normalization

ฟังก์ชัน: `normalize_service_key(value)`

กติกา:

- normalize text
- casefold
- ลบ punctuation ที่ไม่จำเป็น
- แปลง space / hyphen เป็น underscore

ผลที่ได้มีไว้เพื่อ:

- ทำ comparable key
- ใช้ profiling/service grouping ขั้นต้น

ยังไม่ถือเป็น clinical master mapping แบบสมบูรณ์

## Date normalization

ฟังก์ชัน: `parse_service_date(value)`

กติกา:

- ใช้ parser เดียวกับระบบ
- รองรับ Excel datetime / text date
- ถ้า parse ไม่ได้ต้องได้ `invalid_date`
- ถ้าไม่มีค่าต้องได้ `missing_date`

## Safety rules

- ห้ามเขียนทับ raw source values
- ห้ามเดาค่าที่ไม่มี
- ค่าที่ parse ไม่ได้ต้องเห็นเป็น error/warning ได้
- latest date ใน phase ถัดไปต้องคำนวณจาก selected services เท่านั้น ไม่ใช่ประวัติอื่น
