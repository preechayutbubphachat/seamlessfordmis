# Target Group Multi-Sheet Design

## Goal

The target group importer must inspect every sheet in an uploaded workbook.
The system must not assume that only the first sheet matters.

## Sheet Types

The importer now classifies each sheet into one of these explicit types:

- `roster_sheet`
- `history_sheet`
- `mixed_sheet`
- `unknown_sheet`

## Classification Inputs

Classification is conservative and combines:

- sheet name hints
- column names
- whether person identity fields exist
- whether screening or treatment history fields exist

Examples of important fields:

- `CID`
- patient name / `ชื่อผู้ป่วย` / `ชื่อ-สกุล`
- `birth_date` / `วันเกิด`
- `address` / `ที่อยู่`
- `visit_date` / `วันที่ตรวจ`
- `ICD10`
- `HPV`
- result / outcome
- doctor / hospital / note

## Storage

Workbook-level sheet metadata is stored in `target_group_sheets`.
Each sheet record preserves:

- source file
- sheet name
- sheet index
- sheet type
- row count
- column names
- classification confidence
- notes / warnings

History-bearing rows are stored in `target_group_history_rows` with:

- `source_file_id`
- `source_sheet_id`
- `source_sheet_name`
- `source_row_no`

## Result Generation

Result generation now reads evidence from both:

1. disease screening database history
2. target-group-file-side history rows from all eligible sheets

If the disease screening database has no matching history, but any eligible target-group sheet has valid history for that person, the result must not be classified as `no_history_found`.

## Source Precedence

Source precedence remains explicit:

1. disease screening database remains the primary formal source
2. target group file history is valid secondary evidence
3. when both exist, the output records `both_sources`
4. latest relevant date is chosen from the union of eligible records across both sources
