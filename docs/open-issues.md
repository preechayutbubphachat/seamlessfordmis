# Open Issues

1. ~~`/api/target-groups/{group_id}/results` เร็วขึ้นหลังแบ่งหน้าแล้ว แต่ยังคำนวณ summary และ breakdown จากผลทั้งชุดทุกครั้งที่อ่าน~~ **แก้แล้วใน Phase E** — ใช้ aggregate SQL + summary cache table (`target_group_result_summaries`) และ `get_results()` โหลดเฉพาะ target rows ของ page ปัจจุบัน

2. `show all` ถูก guard ไว้ที่ 1,000 รายเพื่อกันหน้าเว็บค้าง ถ้าต้องการมากกว่านี้ควรเพิ่ม server-side pagination/filtering ให้ละเอียดขึ้น

3. target-group-side history ยังเป็น secondary evidence source ทางธุรกิจ ไม่ใช่ confirmed source ระดับเดียวกับ disease screening database

4. name-based identity linking ยังเป็น conservative exact-name fallback และใช้ birth date / address เป็นตัวช่วย ไม่ได้ทำ fuzzy matching — typos หรือรูปแบบชื่อที่แตกต่างกันจะ group เป็น review_required แทน

5. `outside_target_scope` ตอนนี้ใช้ได้เมื่อมี flag ชัดใน source payload หรือเกิดจาก non-Thai nationality; ยังไม่มี business rule เพิ่มเติมสำหรับ scope อื่นที่ซับซ้อน

6. patient detail modal มี endpoint `GET /{group_id}/results/{result_id}/source-history` สำหรับดู two-source history แล้ว (Phase C) แต่ frontend ยังไม่ได้เชื่อม endpoint นี้เข้ากับ modal UI รวมถึง review_required badge ใน Phase D ต้องอัปเดต modal component ให้เรียก source-history endpoint และแสดง canonical_person_key / person_link_status ด้วย

7. multi-sheet target group history ยังใช้ conservative sheet classification; ถ้า workbook ตั้งชื่อ sheet หรือ column แปลกมาก ระบบจะ mark เป็น `unknown_sheet` แทนการนำไปใช้แบบเสี่ยง

8. target-group-side history extraction ยังเน้น explicit service/result fields และ cervical-screening-centric columns ก่อน ยังไม่ได้แตกหลาย event จาก 1 แถวแบบเต็มรูปแบบ

9. unified linked database model ยังอยู่ในสถานะออกแบบ และยังไม่ได้ cutover จาก result snapshot ปัจจุบัน

10. (Phase D) rows ที่ generate ก่อน migration 0011 จะมี `canonical_person_key = NULL` และ fallback ไปใช้ `target_row_id` lookup ซึ่งมีโอกาส miss context หากลำดับ primary row เปลี่ยน — ควร re-generate results หลัง run migration เพื่อ populate ค่าใหม่

11. ~~(Phase D) `view=review_required` filter ใช้ column `review_required` บน TargetGroupResult ได้แล้ว แต่ frontend ยังไม่มี tab/filter button สำหรับ view นี้~~ **แก้แล้วใน Phase E** — เพิ่ม tab "รอยืนยันตัวตน (Phase D)" ใน `VIEW_FILTERS` ของ `TargetGroupResultsWorkspace.tsx` แล้ว

12. (Phase E) history rows (`_load_selected_target_group_history_rows`) ยังโหลด history ทั้งหมดของ group ในทุก paged request — อาจเป็น bottleneck สำหรับ group ที่มี history sheet ขนาดใหญ่ (>5,000 แถว); ควรเพิ่ม server-side filter ให้โหลดเฉพาะ CID ที่อยู่ใน page ปัจจุบัน

13. (Phase E) summary cache ยังไม่ invalidate อัตโนมัติเมื่อ `disease_screening_records` ถูกอัปเดตหลังการ generate — ต้อง re-generate results เพื่อ refresh cache

14. (Phase E) `canonical_person_key` ยังไม่ได้เก็บบน `TargetGroupRow` ดังนั้นการ rebuild full person context (กรณีมีหลาย row ต่อคน) ยังต้องโหลด target rows ทั้งกลุ่ม — Phase F migration จะแก้โดย populate `target_group_membership`

15. (Phase E/F) scaffold tables (`person_master`, `person_identifiers`, `disease_screening_events`, `target_group_membership`) ยังว่างเปล่า — ยังไม่มี data migration (Phase F cutover)
