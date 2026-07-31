# W4 Staging Foundation

This note documents the limited W4 foundation added after W0-W3 verification.

## Scope

- Apply existing migrations to the empty MariaDB dev database.
- Keep import staging as placeholders only.
- Add import job detail route placeholders for future source-file and target-group staging review.

## Explicit Non-Goals

- No real patient data.
- No upload form.
- No Excel or CSV parsing.
- No file storage workflow.
- No import commit action.
- No matching.
- No result generation.
- No export execution.
- No seed data.

## Staging-First Principle

Future import work must preserve raw rows first, validate before commit, show row-level errors, and keep provenance/audit information before any production result is generated.
