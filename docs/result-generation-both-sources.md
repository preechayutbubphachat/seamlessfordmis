# Result Generation — Two-Source Evidence Model (Phase C)

## Overview

Result generation merges evidence from **two independent sources** to determine
whether a target-group person has relevant screening history:

| Source | Table | Key field |
|---|---|---|
| Disease screening database | `disease_screening_records` | `normalized_person_identifier` |
| Target-group file (history sheets) | `target_group_history_rows` | `normalized_cid` |

A person is classified as **having selected history** (`has_selected_service = true`)
when at least one matching record exists in **either** source for any of the
selected service keys.

---

## Why two sources?

The disease screening database is the authoritative record of confirmed clinical
visits. However, hospitals often receive target-group lists that embed previous
screening history directly in the file (e.g., a `history_sheet` or `mixed_sheet`
tab in the uploaded Excel workbook). Before Phase C, persons whose evidence
existed only in the target-group file were incorrectly classified as
`no_history_found`. Phase C fixes this regression.

---

## Evidence loading

### Screening database records

```python
eligible_records = ResultGenerationService._load_eligible_screening_records(
    db, normalized_cid, selected_to_record_keys
)
```

Queries `DiseaseScreeningRecord` by `normalized_person_identifier` (the canonical
13-digit citizen ID), filtered to the `normalized_service_key` values that
correspond to the selected canonical service keys.

### Target-group history rows

```python
eligible_history_rows = ResultGenerationService._load_selected_target_group_history_rows(
    db, target_row, selected_to_record_keys
)
```

Queries `TargetGroupHistoryRow` rows that belong to the same target-group job,
are matched to the current person via `normalized_cid`, and whose
`normalized_service_key` falls within the expanded selected key set.

Only rows with `validation_status != "invalid"` and `parse_status = "parsed"`
are considered.

---

## Date merging

Both sources contribute candidate visit dates. The merged latest date is:

```python
latest_db_visit = max(
    (r.visit_date for r in eligible_records if r.visit_date is not None),
    default=None,
)
latest_tg_visit = max(
    (h.normalized_visit_date for h in eligible_history_rows
     if h.normalized_visit_date is not None),
    default=None,
)
latest_visit = max(
    (v for v in [latest_db_visit, latest_tg_visit] if v is not None),
    default=None,
)
```

`None` dates are explicitly excluded before calling `max()` to prevent a
`TypeError` when any row has a blank visit date (Phase C bug fix).

---

## History source categories

The `history_source_summary` field (and the equivalent `result_category` for
persons with valid evidence) records which source(s) contributed history:

| Value | Meaning |
|---|---|
| `screening_db_only` | Evidence found only in `disease_screening_records` |
| `target_group_file_only` | Evidence found only in `target_group_history_rows` |
| `both_sources` | Evidence found in both sources |
| `no_history_found` | No evidence in either source for the selected services |

### Mapping to `result_status`

For persons with a valid identifier who are in scope, `result_status` is set to
the `history_source_summary` value directly:

```python
result_status = history_source_summary  # one of the four values above
```

---

## `latest_relevant_source_type` field

The response schema includes `latest_relevant_source_type` (added in Phase C)
alongside the existing `last_relevant_source` field. Both carry the same value;
`latest_relevant_source_type` uses the Phase C spec name so the frontend can
consume either without a breaking change.

Possible values:

| Value | Meaning |
|---|---|
| `"screening_db"` | The latest qualifying date came from the disease screening database |
| `"target_group_file"` | The latest qualifying date came from a target-group history sheet |
| `None` | No qualifying date found in either source |

---

## Source-history endpoint

A dedicated endpoint returns the full two-source breakdown for a single result:

```
GET /api/target-groups/{group_id}/results/{result_id}/source-history
    ?service_keys=cervical_screen&service_keys=breast_screen
```

Response schema (`ResultSourceHistoryResponse`):

```json
{
  "result_id": "...",
  "normalized_cid": "1234567890123",
  "full_name": "นางสาว ก",
  "screening_db_records": [
    {
      "record_id": "...",
      "normalized_person_identifier": "1234567890123",
      "normalized_service_key": "cervical_screen",
      "visit_date": "2023-06-01",
      "source_file_name": "screening_jan2024.xlsx",
      "source_row_no": 42
    }
  ],
  "target_group_history_events": [
    {
      "normalized_service_key": "cervical_screen",
      "normalized_visit_date": "2022-11-15",
      "source_file_name": "target_q1.xlsx",
      "source_sheet_name": "ประวัติ"
    }
  ],
  "history_source_summary": "both_sources"
}
```

The frontend uses this endpoint in the patient detail modal when
`history_found_in_target_group_file = true` to display the complete evidence
picture rather than only the screening-database records.

---

## Screening status derivation

After merging both evidence sources, the screening status is derived from the
combined `latest_visit` date:

| Condition | `screening_status` |
|---|---|
| No qualifying evidence | `never_checked` |
| Evidence exists, within threshold | `checked_and_within_threshold` |
| Evidence exists, overdue | `checked_but_overdue` |

The overdue threshold is set by the selected disease configuration
(`overdue_threshold_years`).

---

## Implementation files

| File | Role |
|---|---|
| `backend/app/services/result_generation_service.py` | Core two-source merge logic in `_build_row_result_payload()` |
| `backend/app/services/patient_query_service.py` | `source_history_for_result()` — CID-based two-source lookup |
| `backend/app/api/target_groups.py` | `GET /{group_id}/results/{result_id}/source-history` endpoint |
| `backend/app/schemas/result.py` | `GroupResultRowResponse` — includes `latest_relevant_source_type` |
| `backend/app/schemas/patient.py` | `ResultSourceHistoryResponse`, `ScreeningRecordResponse` |
| `backend/tests/test_result_generation.py` | Tests K.1–K.7 covering two-source scenarios |

---

## Tests (K.1–K.7)

| ID | Description |
|---|---|
| K.1 | Screening DB only → `result_status = "screening_db_only"` |
| K.2 | TG file only → `has_selected_service = True`, `result_status = "target_group_file_only"` (regression fix) |
| K.3 | Both sources → `result_status = "both_sources"`, `matching_record_count = 2` |
| K.4 | Neither source → `has_selected_service = False`, `result_status = "no_history_found"` |
| K.5 | Latest date chosen correctly across both sources (both directions) |
| K.6 | `None` visit dates excluded from `max()` without crash |
| K.7 | Regression guard — TG history prevents `no_history_found` classification |

---

## Safety rules preserved

- TG-file history is evidence, not a confirmed clinical record. It does not
  override the disease screening database for authoritative clinical decisions.
- Rows with `validation_status = "invalid"` are excluded from both evidence
  sources and remain visible in staging for review.
- Blank/null visit dates in TG history rows are preserved in storage but excluded
  from date comparison to avoid crashing the merge.
- `no_history_found` is only set when **both** sources return empty results for
  the selected service keys — never from one source alone.
