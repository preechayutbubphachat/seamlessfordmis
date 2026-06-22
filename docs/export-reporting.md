# Export Reporting

เอกสารนี้อธิบายการ export รายงานของ Phase 8

## Supported Formats

- `xlsx`
- `csv`

Excel เป็นรูปแบบหลักสำหรับใช้งานในหน่วยงาน

## Export Source Of Truth

การ export ใช้ผลลัพธ์ชุดเดียวกับหน้า UI โดยตรง:

- ใช้ `ResultGenerationService.get_results(...)`
- ใช้ summary และ person-level rows ชุดเดียวกัน
- ห้าม recompute สูตร summary อีกชุดระหว่าง export

ดังนั้น:

- summary ในไฟล์ต้องตรงกับ summary ในหน้า
- จำนวนแถวในไฟล์ต้องตรงกับจำนวนแถวผลรายบุคคล
- result category ต้องตรงกับที่ UI แสดง

## Excel Structure

### Sheet 1: Summary

มีข้อมูลเช่น:

- ชื่อกลุ่มเป้าหมาย
- รหัสกลุ่ม
- วันที่สร้างรายงาน
- โรค/บริการที่เลือก
- จำนวนกลุ่มเป้าหมายทั้งหมด
- จำนวนที่มีประวัติในรายการที่เลือก
- จำนวนที่ไม่พบประวัติในรายการที่เลือก
- จำนวนตัวระบุไม่ถูกต้อง / ไม่มีข้อมูลตัวระบุ
- coverage %
- ตัวหารที่ใช้คำนวณ coverage

### Sheet 2: Person Results

มีข้อมูลรายบุคคล เช่น:

- ลำดับ
- CID / ตัวระบุ
- ชื่อ-สกุล
- อายุ
- เพศ
- สถานะผลลัพธ์
- จำนวนครั้งที่พบ
- วันที่ล่าสุด
- ผ่านมาแล้วกี่วัน
- ผ่านมาแล้วกี่ปี
- หมายเหตุ

### Sheet 3: Service Breakdown

ถ้ามีข้อมูล breakdown ที่พร้อมใช้งาน ระบบจะเพิ่ม sheet นี้ให้

## CSV Structure

CSV ใช้ person-level rows เป็นหลัก

เพื่อให้ audit และใช้งานต่อได้ง่าย จะมี context หลักซ้ำในแต่ละแถว เช่น:

- รหัสกลุ่ม
- ชื่อกลุ่มเป้าหมาย
- วันที่สร้างรายงาน
- โรค/บริการที่เลือก
- Coverage (%)

## Label Mapping

- `has_selected_history` -> `พบประวัติในรายการที่เลือก`
- `no_selected_history` -> `ไม่พบประวัติในรายการที่เลือก`
- `invalid_identifier` -> `ตัวระบุไม่ถูกต้อง`
- `missing_identifier` -> `ไม่มีข้อมูลตัวระบุ`
- `needs_review` -> `ต้องตรวจสอบ`

## Context Consistency Rule

ถ้า service ที่เลือกในหน้าไม่ตรงกับผลลัพธ์ล่าสุด:

- ระบบจะไม่ export
- ผู้ใช้ต้องสร้างผลลัพธ์ใหม่ก่อน

เพื่อกันรายงานผิดบริบท

## Known Limitations

- export ยังอิงผลล่าสุดของ group เดียว ไม่ใช่หลาย snapshot พร้อมกัน
- CSV ไม่มี summary sheet แยกแบบ Excel
