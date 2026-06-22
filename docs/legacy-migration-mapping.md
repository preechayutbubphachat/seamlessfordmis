# Legacy Migration Mapping

## Principles

- This is a one-way migration into a fresh current-schema database.
- The legacy database remains read-only during migration.
- Existing IDs may be preserved only if they do not violate current constraints.
- Missing current fields must be synthesized conservatively.
- Result snapshots should be regenerated where practical instead of trusted as final truth.

## `target_group_jobs`

| Current Field | Legacy Source | Rule |
| --- | --- | --- |
| `id` | `target_group_jobs.id` | preserve UUID if possible |
| `import_job_id` | `target_group_jobs.import_job_id` | preserve if migrated import job exists |
| `group_name` | `group_name` | copy |
| `source_file_name` | `original_filename` | fallback `stored_path` basename, then `legacy-target-group-{id}` |
| `source_file_type` | `source_file_type` | fallback infer from filename extension |
| `source_file_hash` | `file_hash_sha256` | fallback 64 zeroes only if source file unavailable, flagged in notes |
| `source_set_hash` | `file_hash_sha256` | one-file legacy assumption unless metadata says otherwise |
| `source_file_count` | none | default `1` |
| `uploaded_by` | `uploaded_by` | copy |
| `parse_status` | `parse_status` / `status` | map `success`, `warning`, `failed`, fallback `pending` |
| `match_status` | `match_status` | copy/fallback `pending` |
| `total_rows` | `total_rows` | copy |
| `parsed_rows` | `valid_rows + invalid_rows + review_rows` | fallback `total_rows` |
| `valid_rows` | `valid_rows` | copy |
| `invalid_rows` | `invalid_rows` | copy |
| `missing_cid_rows` | none | compute from migrated rows |
| `duplicate_cid_rows` | none | compute from migrated rows |
| `warning_rows` | `review_rows` | copy as warning count |
| `failed_rows` | none | default `0` unless row parse failures known |
| `notes` | `notes` + migration context | append legacy migration note |

## `target_group_job_files`

Legacy does not have this table.

Create one synthesized row per migrated target group job:

| Current Field | Legacy Source | Rule |
| --- | --- | --- |
| `group_job_id` | migrated target group job id | required |
| `file_name` | `original_filename` | fallback `stored_path` basename |
| `file_path` | `stored_path` | copy |
| `file_type` | `source_file_type` | fallback extension |
| `sha256` | `file_hash_sha256` | fallback marker hash only with warning |
| `size_bytes` | none | null unless file still exists |
| `source_modified_at` | none | null unless file still exists |
| `parse_status` | job parse status | copy/fallback `parsed` |
| `row_count` | job total rows | copy |
| `warning_count` | job review rows | copy/fallback `0` |
| `parse_error_summary` | `metadata_json` / `notes` | summary if available |

## `target_group_sheets`

Legacy does not have sheet metadata.

Preferred:

1. re-inspect original uploaded files if `stored_path` exists
2. persist real workbook sheet metadata

Fallback:

- create one synthetic sheet:
  - `sheet_name = legacy_unknown_sheet`
  - `sheet_index = 0`
  - `sheet_type = unknown_sheet`
  - `row_count = target_group_jobs.total_rows`
  - `notes = synthesized during legacy migration; original sheet metadata unavailable`

## `target_group_rows`

| Current Field | Legacy Source | Rule |
| --- | --- | --- |
| `id` | `target_group_rows.id` | preserve if possible |
| `group_job_id` | `job_id` | map to migrated job id |
| `source_file_id` | synthesized target group file | required when available |
| `source_file_name` | job/file name | copy |
| `row_no` | `row_number` | copy |
| `source_row_no` | `row_number` | copy |
| `raw_cid` | `citizen_id` or `raw_payload.CID` | normalize later |
| `raw_pid` | `pid` | copy |
| `raw_citizen_id` | `citizen_id` | copy |
| `raw_hn` | `hn` | copy |
| `raw_full_name` | `full_name` | copy |
| `raw_birth_date` | `birth_date` | stringify/copy |
| `raw_age` | `raw_payload.age` / `raw_payload.อายุ` | copy if present |
| `raw_sex` | `raw_payload.sex` / `raw_payload.เพศ` | copy if present |
| normalized identity/name/date fields | derive using current normalization utilities | do not trust legacy raw shape blindly |
| `parse_status` | `parse_status` | copy/fallback `parsed` |
| `validation_status` | `is_valid`, `validation_errors` | `valid`, `invalid`, or `warning` |
| `cid_validation_status` | normalized CID result | current validator decides |
| `duplicate_status` | computed within migrated job | `unique_in_job` / `duplicate_in_job` |
| `match_status` | `match_status` | copy/fallback `pending` |
| `matched_patient_id` | `matched_patient_id` | preserve if migrated patient exists |
| `confidence_flag` | `confidence_flag` | copy |
| `error_message` | `error_message` / `validation_errors` | copy |
| `warning_message` | review/duplicate notes | synthesized |
| `raw_json` | `raw_payload` plus legacy provenance | copy and annotate |

## `target_group_history_rows`

Legacy does not have this table.

Preferred:

1. re-ingest original target files with the current multi-sheet importer
2. let current importer create `target_group_history_rows`

Fallback:

- derive only if `raw_payload` contains explicit service/history fields
- do not infer history from generic notes
- preserve `source_sheet_name` if present in `raw_payload`; otherwise use synthetic legacy sheet

## `diagnosis_history`

Current `diagnosis_history` and current `disease_screening_records` serve different purposes.

### Current `diagnosis_history`

| Current Field | Legacy Source | Rule |
| --- | --- | --- |
| `id` | `diagnosis_history.id` | preserve if possible |
| `patient_id` | `patient_id` | preserve if migrated patient exists |
| `visit_date` | `visit_date` | required |
| `diagnosis_code` | `diagnosis_code` | copy |
| `diagnosis_name` | `disease_name_raw` | copy |
| `normalized_disease_key` | `normalized_disease_key` | copy |
| `department` | `encounter_type` | copy if meaningful |
| `doctor_name` | `provider_name` | copy |
| `source_import_job_id` | `import_job_id` | map migrated job id |
| `source_file_name` | `source_filename` | copy |
| `source_row_no` | `source_row_number` | copy |

### Current `disease_screening_records`

Create from legacy `diagnosis_history` only when required fields are present:

| Current Field | Legacy Source | Rule |
| --- | --- | --- |
| `source_import_job_id` | mapped import job id | required |
| `source_file_id` | synthesized source file id | nullable if unknown |
| `source_file_name` | `source_filename` | copy |
| `source_row_no` | `source_row_number` | copy |
| `raw_person_identifier` | patient `citizen_id`, patient `pid`, or legacy `patient_id` marker | prefer real identifier |
| `normalized_person_identifier` | normalize raw identifier | required for matching |
| `full_name` | joined patient full name | copy |
| `normalized_full_name` | normalize patient full name | copy |
| `raw_service_type` | `disease_name_raw` or `diagnosis_code` | copy |
| `normalized_service_key` | map `normalized_disease_key` through current service mapping | required |
| `visit_date` | `visit_date` | required |

Rows missing identifier, service key, or visit date should remain in staging/review, not production `disease_screening_records`.

## `target_group_results`

Recommendation: do not migrate as active current result rows.

Reasons:

- current output model has selected-service hashes and richer source-aware categories
- legacy results do not know target-group-side history rows
- legacy results may treat missing history differently from the current business rules

Safer approach:

1. archive legacy results as raw audit/export context if needed
2. regenerate current results after target groups and disease screening records are migrated

If a temporary compatibility import is required:

- map `job_id` to `group_job_id`
- map `target_group_row_id` to `target_row_id`
- map `has_disease_history` to `has_selected_service`
- map `visit_count` to `matching_record_count`
- map `latest_visit_date` to `last_visit_date`
- map `days_since_latest_visit` to `days_since_last_visit`
- map `years_since_latest_visit` to `years_since_last_visit`
- set `selected_service_keys` from `selected_disease_key` / `disease_key`
- compute `selected_service_hash`
- mark `warning_message = migrated legacy result; regenerate recommended`

## Open Questions Before Script Implementation

- Are original target group upload files still available at `stored_path`?
- Should legacy `target_group_results` be archived, ignored, or temporarily imported?
- Which legacy disease mapping keys should map to current normalized service keys?
- Should migrated UUIDs be preserved exactly or remapped into new UUIDs?
- Some legacy target rows contain `pid` but no `citizen_id`. Current target group MVP treats `CID` as the primary identifier, so these rows currently dry-run as `missing_identifier`. Confirm whether legacy `pid` should remain review-only or be accepted as a fallback identifier for migrated historical groups.

## Dry-Run Status

`backend/scripts/migrate_legacy_core_dry_run.py` currently covers:

- `patients`
- `import_jobs`
- `target_group_jobs`
- `target_group_rows`

The script is read-only and emits transformed sample rows plus warnings.
It does not insert into the target database.

## Apply Script Status

`backend/scripts/migrate_legacy_core_apply.py` is the first transactional apply script for the core migration.

Current scope:

- `import_jobs`
- `patients`
- `target_group_jobs`
- synthesized `target_group_job_files`
- `target_group_rows`

Safety behavior:

- dry-run rollback is the default
- writes commit only with `--execute`
- `--limit` supports smoke tests against a fresh target database
- the script blocks legacy and target URLs that are exactly the same
- the script blocks non-empty target core tables unless `--allow-non-empty` is passed
- legacy integer IDs are remapped to deterministic UUIDs for the current schema
- duplicate migrated patients by `pid` or `citizen_id` are mapped to the first migrated patient instead of creating obvious duplicates

Smoke test result against `seamlessfordmis_current_dryrun`:

- command: `python backend/scripts/migrate_legacy_core_apply.py --limit 100`
- mode: `dry_run_rollback`
- committed writes: `false`
- target core table counts before and after: `0`
- inserted in transaction before rollback:
  - `import_jobs`: 8
  - `patients`: 100
  - `target_group_jobs`: 7
  - `target_group_job_files`: 7
  - `target_group_rows`: 100

Open warning:

- some legacy target rows contain `pid` but no `citizen_id`, so current mapping keeps those rows as `missing_identifier` under the CID-first MVP rule. Confirm whether legacy `pid` should remain review-only or become a fallback identifier for historical migration.
