# Performance Diagnosis

## Scope Checked

ตรวจสอบ flow ต่อไปนี้โดยวัดจากเครื่อง local เดียวกัน:

- dashboard
- target group detail page
- result generation read path
- person-level results API
- result summary API
- patient detail modal API
- dev mode เทียบกับ production build

## Measurement Environment

- frontend dev: `http://127.0.0.1:3020`
- frontend production test: `http://127.0.0.1:3021`
- backend API: `http://127.0.0.1:8010`
- date of measurement: 2026-04-21
- measurement method: `Invoke-WebRequest` + PowerShell `Stopwatch`

## Findings Summary

### 1. Main Bottleneck Before Fix

ช้าที่สุดคือ person-level results endpoint:

- endpoint: `/api/target-groups/{group_id}/results?overdue_years=1`
- before fix: 28.9s, 34.7s, 29.5s
- payload size: 18,489,772 bytes
- row count in payload: 19,960 rows

Conclusion:

- bottleneck หลักอยู่ที่ backend ส่งข้อมูลผลลัพธ์ทั้งชุดในครั้งเดียว
- frontend ต้อง render และ filter/search บนข้อมูลเกือบ 20,000 แถว
- อาการช้าใน target group detail page, filter change, search และ table scroll มีรากเดียวกันคือ oversized results payload

### 2. Dashboard Is Not the Primary Problem

`/dashboard`

- dev mode: first load ประมาณ 2219ms, warm load ประมาณ 421-441ms
- production mode: ประมาณ 748ms, 423ms, 288ms

Conclusion:

- dashboard มี dev overhead ชัด แต่ไม่ได้เป็น bottleneck ใหญ่เท่า results endpoint

### 3. Target Group Route Was Affected By Dev Mode And Results Payload

Target group detail page route:

- dev mode before result optimization context: ประมาณ 606-1071ms สำหรับ route HTML
- production mode: ประมาณ 194-244ms

Conclusion:

- Next.js dev mode overhead มีผลจริงกับความรู้สึกช้า
- แต่ route HTML เองไม่ใช่ต้นเหตุของอาการค้างยาวหลายสิบวินาที
- อาการหนักเกิดหลัง route เรียกผลลัพธ์รายบุคคลขนาดใหญ่

### 4. Result Summary API Is Relatively Light

`/api/target-groups/{group_id}/result-summary?overdue_years=1`

- before optimization round: ประมาณ 836-1281ms
- after optimization round: ประมาณ 768-1162ms
- payload size: 624 bytes

Conclusion:

- summary API ไม่ใช่จุดคอขวดหลัก
- ยังมีต้นทุนคำนวณอยู่ แต่ payload เบาและใช้ได้สำหรับ summary card

### 5. Patient Detail Modal Is Not The Main Bottleneck

`/api/patients/{patient_id}/history`

- before: ประมาณ 37-331ms
- after restart with current code: ประมาณ 13-111ms
- payload size: 876 bytes

Conclusion:

- modal history load แบบ lazy on-demand ทำงานได้เร็วพอ
- ไม่ใช่ priority bottleneck สำหรับรอบนี้

## Dev Mode vs Production Build

ผลเปรียบเทียบชัดว่าการรัน frontend แบบ production ช่วยลด latency ของ route render:

- target group detail route ใน production เหลือประมาณ 165-454ms
- dev mode route เดิมอยู่ระดับหลายร้อย ms ถึงเกิน 1s

Conclusion:

- dev mode overhead เป็นปัจจัยจริง โดยเฉพาะเวลา compile/hydrate route ครั้งแรก
- แต่แม้ production จะเร็วขึ้น ก็ไม่สามารถอธิบายผลลัพธ์ API 29-35s ได้
- จึงสรุปว่า dev overhead เป็น secondary factor ไม่ใช่ root cause หลัก

## Evidence-Based Bottleneck Classification

### Slow Page / Interaction

1. target group results load
   - slow when: page load, filter, search, table review
   - bottleneck: backend API payload size + frontend rendering cost
   - evidence: results endpoint 18.5 MB and ~29-35s before fix

2. target group detail route in dev
   - slow when: first route load
   - bottleneck: dev mode overhead
   - evidence: dev route slower than production route by large margin

3. patient detail modal
   - slow when: not materially slow
   - bottleneck: none critical
   - evidence: API response mostly sub-100ms after warm-up

4. dashboard
   - slow when: first dev load only
   - bottleneck: dev mode overhead more than backend
   - evidence: production route significantly faster

## Remaining Performance Risks

- results endpoint หลังแบ่งหน้าแล้ว ยังต้องคำนวณ summary และ breakdown จาก snapshot ทั้งกลุ่มทุกครั้ง
- เมื่อมีหลายกลุ่มขนาดใหญ่พร้อมกัน อาจยังมี read amplification ฝั่ง backend/database
- ยังไม่มี aggregate cache หรือ materialized summary layer

## Phase E Optimization Results (2026-05-04)

### Summary Endpoint After Cache Table

- `GET /result-summary` now reads from `target_group_result_summaries` (one primary-key lookup)
- Expected: sub-50 ms for groups of any size
- Fallback: aggregate SQL via `_build_summary_from_sql()` for groups generated before migration 0012

### Results Endpoint Context Rebuild Fixed

- Before Phase E: `get_results()` loaded ALL `TargetGroupRow` records for the group on every paged
  request in order to rebuild person contexts.  For a 20,000-row group this added ~4-6 s.
- After Phase E: only the `target_row_id` values on the current page's `TargetGroupResult` rows are
  loaded (O(page_size) instead of O(total_rows)).  Phase D stored fields (`person_link_status`,
  `review_required`, `duplicate_reason`) are read directly from the result — no recomputation needed.

### Performance Index Coverage Added (migration 0013)

New composite indexes:

| Table | Index | Purpose |
|---|---|---|
| `target_group_results` | `idx_tgr_group_result_status` | view= filter (status within group) |
| `target_group_results` | `idx_tgr_group_has_history` | has_selected_service filter |
| `disease_screening_records` | `idx_dsr_identifier_service_key` | two-column evidence lookup |
| `target_group_history_rows` | `idx_tghr_group_cid_service` | history lookup by CID + service |
| `target_group_history_rows` | `idx_tghr_group_name_service` | history lookup by name + service |

### Remaining Risks After Phase E

- History rows (`_load_selected_target_group_history_rows`) still loads all matching history for the
  group on every paged result request — this is acceptable for moderate-size groups but may become a
  bottleneck for groups with large history sheets (>5 000 history rows).
- The `_build_breakdown_from_screening()` call uses a single representative row and may give
  inaccurate breakdown counts if results for a group were generated with mixed service keys.
- Summary cache is invalidated by re-generation, but not automatically invalidated if the
  underlying `disease_screening_records` table is updated after generation.
