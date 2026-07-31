# W12.4 Session Authentication and RBAC Foundation

W12.4 provides Laravel session login/logout and fail-closed role-based permission enforcement without adding public registration, password reset, default users, credentials, export generation, or downloads.

## Authentication

The login identifier is the unique `users.email` field. Passwords use Laravel's existing hashed cast and session guard. Successful login regenerates the session ID and redirects only to the internal dashboard route. Logout invalidates the session and regenerates the CSRF token. Login attempts are limited to five failures per normalized email and source IP per minute.

Routes are limited to `GET /login`, `POST /login`, and authenticated `POST /logout`. Guest middleware protects login routes. There is no GET logout, registration, password reset, remember-me, external redirect input, or default credential.

## RBAC

Persisted authorization follows `users -> role_user -> roles -> permission_role -> permissions`. Permission names use exact lowercase dotted identifiers. Empty, unknown, mixed-case, wildcard, substring, malformed, or database-error checks fail closed. No administrator bypass exists.

The `permission` middleware alias is registered for future server-side use as `permission:export.generate`. W12.4 does not apply it to exports and does not add `/exports/generate`; W12.5 remains a separate gate.

`SystemPermissionSeeder` idempotently registers only `export.generate`. It does not create users, passwords, roles, role assignments, or alter unrelated permissions. Broader protection of existing admin/import/result/export routes requires a separate hardening gate.
