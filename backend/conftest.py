"""
conftest.py — backend test root
================================
Marks backend/ as the pytest rootdir so that `app.*` imports resolve
correctly without installing the package.

No fixtures are defined here — all test-specific setup lives in the
individual test files.

Safety rules (apply to all tests in this project):
- Do NOT import app.db.session at module level in any test file —
  session.py creates a SQLAlchemy engine on import, which attempts
  a PostgreSQL connection. Tests that use SQLite create their own engines.
- Do NOT use real patient CIDs, names, or database credentials.
- Fixture files under tests/fixtures/desktop_local/ contain SYNTHETIC data only.
"""
