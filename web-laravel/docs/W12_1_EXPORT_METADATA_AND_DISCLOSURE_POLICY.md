# W12.1 Export Metadata and Disclosure Policy

W12.1 adds nullable artifact metadata columns to `export_jobs` and defines a disclosure policy for a later private CSV generation gate. It does not generate files, expose downloads, enable `POST /exports`, or change W11 preview behavior.

## Artifact metadata

Artifact metadata belongs in dedicated `export_jobs` columns, not in the filter snapshot:

- `generated_filename`: server-generated filename only
- `mime_type`: artifact media type
- `byte_count`: measured artifact size
- `sha256`: SHA-256 of finalized artifact bytes

All fields are nullable so blocked, pending, failed, and historical rows remain valid. SHA-256 is intentionally not unique because separate export jobs may produce identical content.

## Disclosure policy

Policy version: `deidentified_internal_v1`

The deterministic future CSV column order is:

1. `export_sequence`
2. `result_category`
3. `review_status`
4. `latest_history_date`
5. `latest_history_source`
6. `evidence_source_count`
7. `provenance_available`
8. `selected_service_keys`
9. `target_group_job_id`
10. `result_generation_job_id`

The policy rejects unknown fields and identifying or sensitive fields, including CID variants, names, birth date, addresses, phone numbers, credentials, raw payloads, complete provenance JSON, uploaded source-row contents, absolute storage paths, and free-form `review_reason`. A mixed allowed/prohibited selection fails completely; prohibited fields are never silently removed.

## Identified export boundary

W12.1 and the next W12 private CSV implementation are deidentified only. CID and name export are not authorized.

Any identified export requires a separate roadmap gate with authentication, explicit permission or role, purpose-of-use policy, audit, private download authorization, retention policy, and explicit business approval.
