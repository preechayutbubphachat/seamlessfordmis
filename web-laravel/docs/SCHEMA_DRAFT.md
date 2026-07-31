# MariaDB Schema Draft

This schema is W1 skeleton only. It creates the storage shape needed for safe staging, validation, provenance, audit, and later result generation.

## Core Groups

- Auth and permissions: Laravel generated `users` table, plus W1 `roles`, `permissions`, `role_user`, `permission_role`
- Audit: `audit_logs`
- Disease/service catalog: `disease_services`, `disease_service_aliases`
- Source screening staging: `source_import_jobs`, `source_import_files`, `source_import_rows`
- Target group staging: `target_group_jobs`, `target_group_files`, `target_group_rows`, `target_group_history_rows`
- Result generation: `result_generation_jobs`, `target_group_results`, `target_group_result_sources`
- Export jobs: `export_jobs`

## Safety Design

- Staging rows preserve `raw_payload`.
- CID fields keep raw and normalized values separate.
- Validation status and review reason are stored at row level.
- Result evidence is stored in source/provenance tables.
- Upload duplicate guards use `sha256`.
- Export jobs store only metadata and ignored storage paths.

## W4.5 Schema Decisions

- Laravel's generated `users` table is canonical.
- W1 auth/permission migrations must not recreate `users`.
- Import staging models are metadata contracts only; they must not parse, store, or import files.
- Result tables already reserve evidence/provenance fields for W5, but W5 matching and result generation are not implemented in W4.

## W5-Reserved Evidence Fields

`target_group_results` keeps summary evidence fields:

- `selected_service_keys`
- `evidence_summary`
- `latest_history_date`
- `latest_history_source`
- `review_status`
- `review_reason`

`target_group_result_sources` keeps row-level provenance fields:

- `source_type`
- `source_file_id`
- `sheet_name`
- `row_number`
- `source_payload`
- `evidence_date`
- `normalized_service_key`
- `provenance`
