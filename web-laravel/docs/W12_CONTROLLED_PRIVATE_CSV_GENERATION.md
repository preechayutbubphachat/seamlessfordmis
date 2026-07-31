# W12 Controlled Private CSV Generation

W12 generates a private, deidentified CSV only through `ExportService`. It adds no web trigger, download route, public URL, controller behavior, command, or spreadsheet package. `POST /exports` remains disabled.

## Disclosure and source contract

The service validates the complete header through `deidentified_internal_v1`. The exact order is `export_sequence`, `result_category`, `review_status`, `latest_history_date`, `latest_history_source`, `evidence_source_count`, `provenance_available`, `selected_service_keys`, `target_group_job_id`, and `result_generation_job_id`.

Rows come only from persisted `target_group_results`. Related `target_group_result_sources` contribute only a count and availability flag. `selected_service_keys` comes from the persisted `result_generation_jobs` context, is sorted, and is serialized as a JSON array. Staging tables, uploaded content, result drafts, and result-generation services are not read.

Results are ordered by `target_group_results.id` ascending. One result produces one row. `evidence_source_count` counts all stored source records related to that result; multiple source records do not multiply result rows. `provenance_available` is `true` when that count is greater than zero.

## CSV format

- UTF-8 with exactly one BOM for controlled Thai/Excel compatibility
- comma delimiter and double-quote enclosure
- explicit empty escape argument to `fputcsv`
- CRLF record endings and a final CRLF
- server-generated filename with no request or identifying data

## Lifecycle and storage

One `export_jobs` row represents one artifact-generation attempt: `pending` to `generating` to `completed`, or `failed`. The artifact is written to a random temporary file under private `storage/app/exports`, flushed, closed, and atomically renamed. Completion is recorded only after row count, byte count, and SHA-256 verification. `stored_path` is storage-relative and `generated_filename` contains the basename only.

A retry of a completed job verifies the existing file, byte count, and SHA-256 and then reuses its metadata without rewriting or creating another success audit. A missing or corrupted completed artifact is marked failed and is never silently overwritten. A separate explicit request creates a separate export job even when filters are identical.

On generation failure, temporary and attempt-owned final files are removed, completed metadata stays null, the job is marked failed with a controlled reason, and no success audit is written. A successful generation records one `export_csv_generated` audit containing operational metadata only.
