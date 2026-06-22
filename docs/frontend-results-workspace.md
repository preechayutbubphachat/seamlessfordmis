# Frontend Results Workspace

## โครงสร้างใหม่ของพื้นที่ผลลัพธ์

ลำดับการใช้งานในหน้า `target-groups/[id]` ถูกจัดใหม่เป็น:

1. ส่วนเลือกโรค/บริการและสั่งสร้างผลลัพธ์
2. สรุปภาพรวมกลุ่มเป้าหมาย
3. พื้นที่ `ตารางติดตามผล`
4. แท็บหมวดผลลัพธ์แบบ compact
5. filtered summary ของรายการที่กำลังแสดง
6. filter bar สำหรับ overdue + search
7. ตารางผลรายบุคคล
8. modal รายละเอียดผู้ป่วย

## พฤติกรรมของ table filters

### result category tabs

- ทั้งหมด
- ตรวจแล้วแต่เกินกำหนด
- ตรวจแล้วและยังไม่เกินกำหนด
- ยังไม่เคยตรวจ
- ตัวระบุไม่ถูกต้อง
- ไม่มีข้อมูลตัวระบุ
- ต้องตรวจสอบ

แท็บเหล่านี้วางไว้ด้านบนของ workspace ตารางโดยตรง และย่อขนาดให้กะทัดรัดเพื่อไม่แย่งสายตาจากข้อมูลตาราง

### overdue toggle

ฟิลเตอร์ `ใช้เงื่อนไขตรวจเกินกำหนด` เป็น local UI filter เพิ่มเติม

- ถ้าปิด toggle:
  - ไม่ใช้ overdue threshold มาคัดแถวในตาราง
- ถ้าเปิด toggle:
  - จะกรองเฉพาะแถวที่มีประวัติและ `years_since_last_visit >= threshold`
  - แถวที่ไม่มีประวัติ หรือแถว invalid/missing identifier จะไม่ถูกนับเป็น overdue

### overdue input

- ผู้ใช้พิมพ์จำนวนปีเองได้
- มี preset 1, 3, 5 ปี
- ใช้ค่าจำนวนเต็มบวกเท่านั้น

### search

ค้นหาร่วมกับแท็บหมวดและ overdue filter ได้ โดยค้นจาก:

- CID / ตัวระบุ
- ชื่อ-สกุล
- matched identifier / matched name basis
- source file name

## filtered summary formula

สรุปย่อยในส่วนตารางใช้ `total_target_people` เป็น denominator เสมอ

```text
shown_count = จำนวนแถวหลังผ่าน category tab + overdue toggle + search
shown_percent = (shown_count / total_target_people) * 100
remaining_count = total_target_people - shown_count
remaining_percent = (remaining_count / total_target_people) * 100
```

ตัวอย่าง:

- แสดง 860 จาก 19,960 ราย (4.31%)
- เหลือ 19,100 ราย (95.69%)

## provenance display

ตารางแสดง provenance แบบย่อในคอลัมน์หมายเหตุ/ที่มาข้อมูล เมื่อแถวนั้น:

- ต้องตรวจสอบ
- ตัวระบุไม่ถูกต้อง
- ไม่มีข้อมูลตัวระบุ
- ใช้ `name_exact_secondary`
- หรือมี warning message

ข้อมูล provenance ที่ใช้:

- ไฟล์ต้นทาง
- แถวต้นทาง
- วิธีจับคู่

รายละเอียดเต็มดูได้ใน modal

## patient detail modal

modal เปิดจากปุ่ม `ดูรายละเอียด` ในแต่ละแถว

ภายใน modal แยกชัดเป็น:

- ข้อมูลผู้รับบริการ
- สรุปประวัติที่ยืนยันจากฐานข้อมูลการตรวจโรค
- ที่มาข้อมูล / provenance
- ข้อมูลจากไฟล์กลุ่มเป้าหมาย
- ประวัติการตรวจ/บริการของผู้ป่วยจาก API

หลักการสำคัญ:

- confirmed screening history ต้องแยกจาก target-group-side context
- modal fetch patient history เฉพาะตอนเปิด และเฉพาะแถวที่มี `patient_id`
