# W12.5 Authenticated Deidentified Export Trigger

W12.5 adds one CSRF-protected synchronous web trigger for the existing W12 private CSV service. It does not provision accounts, add downloads, expose artifact paths, change the disclosure policy, add queues, or alter the existing disabled `POST /exports` contract.

## Authorization and request contract

`POST /exports/generate` requires both `auth` and `permission:export.generate`. The authenticated session user is the only source of `requested_by_user_id`. The request requires explicit confirmation, an existing target-group job, an existing result-generation job belonging to that target-group job, and optional distinct categories from the five stored-result categories.

User IDs, roles, permissions, filenames, paths, columns, policy overrides, download/public options, raw filters, SQL, and sort expressions are prohibited request fields. Policy `deidentified_internal_v1` is set server-side.

The controller recalculates W11 eligibility immediately before calling `ExportService::createAndGenerateCsvExport`. CSV writing, provenance aggregation, lifecycle management, SHA-256 calculation, private storage, and the single `export_csv_generated` audit remain inside W12 services.

## UI and privacy boundary

The generation form appears only for authenticated users with `export.generate`. It states that CID, names, birth dates, `review_reason`, and `raw_payload` are excluded; persisted results are the only source; storage is private; and download is unavailable.

Browser responses expose only safe status information. They never contain CSV bytes, generated filenames, storage paths, absolute filesystem paths, or patient-level values. Account creation, role assignment, public registration, and credential provisioning remain outside this gate.

Generation is synchronous for this controlled development milestone only. Production-scale exports require a later queue/background-worker gate.
