# W0-W2 Scope

## Roadmap Understanding

The Web Server Edition must be a new Laravel + MariaDB application under `web-laravel/`. It must preserve the D4 business rules while moving toward a staging-first, auditable, provenance-aware workflow.

Core rules to preserve:

- CID must be exact 13 digits with Thai citizen ID check digit validation.
- Invalid CID is `invalid_identifier`; missing CID is `missing_identifier`.
- Target-group-file-side history is valid evidence, not `no_history`.
- Latest history date must come only from the selected disease/service.
- Visible result table remains 1 person = 1 row.
- Duplicate upload guard uses stable content SHA256, not filename/path/mtime.
- Raw values, normalized values, row-level validation, provenance, and audit logs are required.
- Export must reflect stored results only.

## In Scope Now

- Safe `web-laravel/` foundation files.
- MariaDB migration skeletons for core tables.
- Service skeletons for W2 classes.
- Unit test skeletons for safe CID/hash logic using synthetic values only.
- Documentation of scope, schema, safety, and current blockers.

## Out of Scope Now

- W3 auth UI/scaffolding and protected routes.
- W4 upload parsing/import execution.
- W5 matching/result generation behavior.
- Real data import.
- Deployment.
- Installer work.
- Git history cleanup.
- Changes to existing `backend/` or `frontend/`.

## Proposed File Structure

```text
web-laravel/
  app/
    Services/
      CidValidator.php
      FileHashService.php
      Audit/AuditLogger.php
      Import/StagingImportService.php
      Import/SourceImportService.php
      Import/TargetGroupImportService.php
      Result/ResultGenerationService.php
      Export/ExportService.php
  database/
    migrations/
  docs/
  tests/
    Unit/
```
