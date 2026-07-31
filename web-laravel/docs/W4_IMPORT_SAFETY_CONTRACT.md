# W4 Import Safety Contract

## Schema Decision

Laravel's generated `users` table is canonical for the Web Edition foundation. The W1 auth/permission migration must not recreate `users`; it only adds role and permission tables that can reference the generated user table later.

## Import Contract

W4 import routes are placeholders only until a validated staging workflow is implemented.

- Import execution is not enabled in W4.
- No file is stored.
- No patient data is imported.
- No Excel or CSV parsing is performed.
- No import rows are created by placeholder actions.

The POST placeholders return HTTP 501 to make the disabled state explicit.
