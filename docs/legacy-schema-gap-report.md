# Legacy Schema Gap Report

## Scope

This report compares the current production-like database `seamlessfordmis` against the active ORM/migration model in `backend/app/models`.

The goal is to prepare a non-destructive migration plan.

## Current Legacy Row Counts

| Table | Rows |
| --- | ---: |
| `import_jobs` | 8 |
| `patients` | 7,267 |
| `staging_history_records` | 99,936 |
| `diagnosis_history` | 16,656 |
| `target_group_jobs` | 7 |
| `target_group_rows` | 13,698 |
| `target_group_results` | 6,853 |
| `disease_mapping` | 21 |

## Compatibility Summary

| Area | Legacy Status | Migration Direction |
| --- | --- | --- |
| `import_jobs` | partially compatible | transform into current `import_jobs` |
| `patients` | mostly compatible | copy with `sex = null`; preserve `normalized_name` in audit/context if needed |
| `diagnosis_history` | partially compatible | migrate to both current `diagnosis_history` and `disease_screening_records` where sufficient |
| `staging_history_records` | legacy staging shape | optional archival or re-stage into current staging only if needed |
| `target_group_jobs` | partially compatible | transform into current `target_group_jobs` |
| `target_group_rows` | incompatible enough to require transform | map raw fields into current raw/normalized fields conservatively |
| `target_group_results` | legacy result shape | do not trust as current result snapshot; regenerate if possible |
| `source_files` | missing | synthesize from legacy import/job/file fields |
| `target_group_job_files` | missing | synthesize one file per legacy target group job |
| `target_group_sheets` | missing | synthesize minimal `unknown_sheet` / legacy source sheet rows when available |
| `target_group_history_rows` | missing | re-ingest original target files if possible; otherwise derive only from explicit legacy fields |
| `disease_screening_records` | missing | derive from `diagnosis_history` and/or valid staging rows |

## Critical Incompatibilities

### Target Group Jobs

Legacy fields:

- `original_filename`
- `stored_path`
- `file_hash_sha256`
- `status`
- `review_rows`
- `metadata_json`
- `confirmed_at`
- `matched_at`

Current fields:

- `source_file_name`
- `source_file_hash`
- `source_set_hash`
- `source_file_count`
- `parsed_rows`
- `missing_cid_rows`
- `duplicate_cid_rows`
- `warning_rows`
- `failed_rows`

Migration must synthesize missing current summary fields instead of copying blindly.

### Target Group Rows

Legacy uses:

- `job_id`
- `row_number`
- `raw_payload`
- `citizen_id`
- `full_name`
- `birth_date`
- `is_valid`
- `validation_errors`

Current uses:

- `group_job_id`
- `row_no`
- `source_file_id`
- `source_file_name`
- `source_row_no`
- raw and normalized CID/name/birthdate/age/sex fields
- explicit validation statuses
- `raw_json`

This is a transform, not an in-place rename.

### Target Group Results

Legacy stores one result style:

- `selected_disease_key`
- `has_disease_history`
- `latest_visit_date`
- `visit_count`
- `days_since_latest_visit`
- `years_since_latest_visit`

Current stores selected-service context:

- `selected_service_keys`
- `selected_service_hash`
- `has_selected_service`
- `matching_record_count`
- `last_visit_date`
- `days_since_last_visit`
- `years_since_last_visit`

Recommendation: preserve legacy results for audit only, then regenerate current results from migrated target rows and disease screening records.

## Recommended Compatibility Labels

- `patients`: partially compatible
- `disease_mapping`: partially compatible, but column names differ and may need reseed
- `diagnosis_history`: partially compatible
- `target_group_jobs`: partially compatible
- `target_group_rows`: partially compatible but transform-heavy
- `target_group_results`: partially compatible but should be regenerated
- `source_files`: missing in legacy
- `target_group_job_files`: missing in legacy
- `target_group_sheets`: missing in legacy
- `target_group_history_rows`: missing in legacy
- `disease_screening_records`: missing in legacy

## Safety Recommendation

Do not run Alembic directly on `seamlessfordmis`.

Use this safer path:

1. create a new target database
2. run current `backend/alembic upgrade head`
3. copy reference data
4. transform legacy data into current schema with explicit scripts
5. compare counts and sampled records
6. switch application configuration only after validation
