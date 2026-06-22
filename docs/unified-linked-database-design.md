# Unified Linked Database Design

## Goal

ออกแบบ internal linked model ที่อ่านเร็วกว่าเดิมสำหรับ:

- matching
- patient detail lookup
- result summary
- disease/service filtering
- provenance review

โดยยังรักษากติกาสำคัญ:

- exact citizen ID match มาก่อน
- secondary name match เป็น fallback เท่านั้น
- conflicting identity ต้องยัง review ได้
- ไม่ overwrite ข้อมูลคนไข้จากหลายแหล่งแบบเงียบ ๆ

## Design Principles

1. staging-first import ยังคงอยู่
2. linked model สร้างหลัง validation และ matching แล้ว
3. canonical person ต้องแยกจาก raw source rows
4. source provenance ต้องย้อนกลับได้ถึง file และ row
5. read-heavy UI ควรใช้ snapshot/summary tables ที่ออกแบบมาเพื่อ query

## Proposed Tables

### 1. person_master

Canonical person record สำหรับงาน read/query

Suggested fields:

- `person_id`
- `canonical_cid`
- `canonical_name`
- `sex`
- `birth_date`
- `nationality`
- `address`
- `canonical_data_status`
- `created_at`
- `updated_at`

Notes:

- canonical fields ควรได้จาก deterministic precedence rules
- ถ้ามี conflict ที่ยังตัดสินไม่ได้ ให้เก็บสถานะเป็น review-needed แทนการเลือกทับ

### 2. person_identifiers

เก็บตัวระบุหลายชนิดต่อคนเดียว

Suggested fields:

- `person_identifier_id`
- `person_id`
- `identifier_type`
- `identifier_value_normalized`
- `source_type`
- `source_file_id`
- `source_row_no`
- `confidence`
- `active_flag`
- `created_at`

Use cases:

- exact CID match
- disease history identifier trace
- future support for HN / PID / other identifiers

### 3. person_source_attributes

เก็บข้อมูลบุคคลจากหลายแหล่งโดยไม่บังคับรวมทับทันที

Suggested fields:

- `person_source_attribute_id`
- `person_id`
- `attribute_name`
- `attribute_value`
- `source_type`
- `source_file_id`
- `source_row_no`
- `is_current`
- `confidence`
- `created_at`

Examples:

- nationality
- address
- phone
- village
- target-group-side health context

### 4. disease_screening_events

Fact table สำหรับประวัติการตรวจ/รับบริการ

Suggested fields:

- `screening_event_id`
- `person_id`
- `service_key`
- `service_label_raw`
- `visit_date`
- `hcode`
- `transaction_id`
- `rep_no`
- `source_file_id`
- `source_row_no`
- `created_at`

Notes:

- latest visit logic ควร query จาก table นี้โดยตรง
- ใช้เฉพาะ selected services เท่านั้นเวลา MAX(visit_date)

### 5. target_group_membership

เชื่อม target group job กับ person ที่ link แล้ว

Suggested fields:

- `target_group_member_id`
- `group_job_id`
- `person_id` nullable
- `raw_cid`
- `normalized_cid`
- `raw_full_name`
- `match_method`
- `match_confidence`
- `result_category`
- `source_file_id`
- `source_row_no`
- `created_at`

Notes:

- ถ้า link ไม่ได้ ยังเก็บ membership row ได้
- ถ้า link แบบ secondary name match ต้องติดธงชัด

### 6. target_group_person_result

Snapshot สำหรับ UI read path

Suggested fields:

- `result_snapshot_id`
- `group_job_id`
- `person_id` nullable
- `target_group_member_id`
- `selected_service_hash`
- `selected_service_keys`
- `result_category`
- `screening_status`
- `has_selected_service`
- `matching_record_count`
- `last_visit_date`
- `days_since_last_visit`
- `years_since_last_visit`
- `warning_message`
- `generated_at`

### 7. target_group_result_summary

Summary table สำหรับ summary cards และ export header

Suggested fields:

- `summary_id`
- `group_job_id`
- `selected_service_hash`
- `selected_service_keys`
- `total_target_people`
- `valid_identifier_people`
- `invalid_identifier_people`
- `people_with_selected_history`
- `people_without_selected_history`
- `never_checked_people`
- `checked_but_overdue_people`
- `checked_and_within_threshold_people`
- `coverage_percent`
- `coverage_denominator_people`
- `generated_at`

## Matching / Linking Rules In The Linked Model

Precedence:

1. exact normalized identifier match
2. secondary exact normalized full-name match only when identifier-based match is unavailable
3. otherwise `not_found` or `needs_review`

Required stored fields:

- `match_method`
- `match_confidence`
- `matched_identifier_basis`
- `matched_name_basis`
- `review_reason`

No silent merge rule:

- หาก candidate identity ขัดกัน ให้แยกไว้ review ได้ ไม่รวมเข้าคนเดียวกันอัตโนมัติ

## Handling Multi-Source Patient Details

### Nationality / Address

รอบปัจจุบัน:

- ดึงจาก `target_group_rows.raw_json` เมื่อมีข้อมูล
- แสดงใน patient detail modal พร้อมบอกว่าเป็นข้อมูลจาก target group source

รอบ linked model:

- เก็บลง `person_source_attributes`
- สร้าง canonical value เฉพาะเมื่อมี deterministic precedence rule
- ถ้ามี conflict ให้แสดงหลายค่าได้พร้อม provenance

## Recommended Indexes

### Must-Have Read Indexes

- `person_master(canonical_cid)`
- `person_identifiers(identifier_value_normalized)`
- `disease_screening_events(person_id, service_key, visit_date desc)`
- `target_group_membership(group_job_id, person_id)`
- `target_group_membership(group_job_id, normalized_cid)`
- `target_group_person_result(group_job_id, selected_service_hash, screening_status)`
- `target_group_person_result(group_job_id, selected_service_hash, result_category)`
- `target_group_result_summary(group_job_id, selected_service_hash)`

### Why These Indexes Matter

- fast exact identifier lookup
- fast latest-visit query within selected services
- fast group-level summary reads
- fast category filtering for UI tabs
- fast patient detail modal lookup by linked person

## Migration Strategy

### Phase A

- keep current tables as source-of-truth operational layer
- add linked tables in parallel
- backfill linked records from existing patients, target groups, disease screening data

### Phase B

- route summary and person-level result reads to new snapshot tables
- keep old tables for audit and reconciliation

### Phase C

- gradually shift matching and result generation to linked model
- retain raw source and staging provenance permanently

## What Should Not Be Done In One Unsafe Jump

- replacing current source tables immediately
- auto-merging all people by name only
- overwriting patient detail conflicts into one canonical row without trace
- moving export to a different formula than current UI

## Recommended First Implementation Step For This Design

เริ่มจากเพิ่ม linked read model แบบไม่กระทบระบบเดิม:

1. create `target_group_result_summary`
2. create `target_group_person_result`
3. backfill from current `TargetGroupResult`
4. switch results read endpoint to summary/snapshot tables first

แนวทางนี้ให้ performance win ก่อน โดยไม่ต้อง cutover identity model ทั้งหมดในครั้งเดียว


---

## Phase E Status (2026-05-04)

### Scaffold Tables Created (migration 0013)

The following four empty scaffold tables have been added to the schema:

| Table | Purpose |
|---|---|
| `person_master` | One row per deduplicated real-world person; holds canonical CID, name, birth date |
| `person_identifiers` | All known identifier values (citizen_id, name+birthdate) per person |
| `disease_screening_events` | Normalized events from `disease_screening_records`, linkable to `person_master` |
| `target_group_membership` | Links each `target_group_rows` row to its `person_master` entry |

All tables are empty — no data migration has run.  They exist so the foreign-key graph is
established and the schema is reviewable before Phase F data migration begins.

### `canonical_person_key` Bridge

`TargetGroupResult.canonical_person_key` (added in Phase D, migration 0011) stores the same key
value that will become the lookup key into `person_master.canonical_person_key`.  This means:

- Phase F can populate `person_master` by reading distinct `canonical_person_key` values from
  `target_group_results`
- No join ambiguity: the key is deterministic and already stored on every result generated after
  migration 0011

### What Remains Before Phase F Cutover

1. Run data migration to populate `person_master` from `target_group_results.canonical_person_key`
2. Populate `person_identifiers` from target group rows and disease screening records
3. Populate `target_group_membership` to link each `target_group_rows` row to a `person_master` row
4. Populate `disease_screening_events` from `disease_screening_records`
5. Update `get_results()` to read provenance from `target_group_membership` instead of rebuilding
   from raw target rows — this enables the full multi-row provenance for deduplicated persons
6. Re-generate results for groups with `canonical_person_key = NULL` (open-issue #10)

See: `docs/legacy-db-migration-strategy.md` for migration safety rules.
