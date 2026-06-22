#!/usr/bin/env bash
# =============================================================================
# verify_phase_e.sh
# Run this from your LOCAL machine (where PostgreSQL is running).
# Usage:
#   cd seamlessfordmis/backend
#   bash ../scripts/verify_phase_e.sh
# =============================================================================
set -euo pipefail

DB_URL="${DATABASE_URL:-postgresql+psycopg://postgres:postgres@localhost:5432/seamlessfordmis}"
# Strip the driver prefix for psql
PSQL_URL="${DB_URL/postgresql+psycopg:\/\//postgresql://}"

echo "============================================================"
echo " Phase E migration + verification script"
echo " DB: ${PSQL_URL%%@*}@..."
echo "============================================================"
echo ""

# ── 1. Activate venv if it exists ────────────────────────────────────────────
if [ -f ".venv/bin/activate" ]; then
  echo "[1/7] Activating .venv..."
  source .venv/bin/activate
else
  echo "[1/7] No .venv found — using system Python/alembic."
fi

# ── 2. Check current alembic state ───────────────────────────────────────────
echo ""
echo "[2/7] Alembic current head / applied revisions:"
alembic current
alembic heads

# ── 3. Run migrations ────────────────────────────────────────────────────────
echo ""
echo "[3/7] Running: alembic upgrade head"
alembic upgrade head
echo "  → upgrade complete."

# ── 4. Verify schema via psql ────────────────────────────────────────────────
echo ""
echo "[4/7] Verifying new tables and indexes..."
psql "${PSQL_URL}" <<'SQL'
-- Tables added by Phase E
SELECT
  tablename,
  'EXISTS' AS status
FROM pg_tables
WHERE schemaname = 'public'
  AND tablename IN (
    'target_group_result_summaries',
    'person_master',
    'person_identifiers',
    'disease_screening_events',
    'target_group_membership'
  )
ORDER BY tablename;

-- Phase E composite indexes
SELECT
  indexname,
  tablename,
  'EXISTS' AS status
FROM pg_indexes
WHERE schemaname = 'public'
  AND indexname IN (
    'idx_tgrs_group_service_hash',
    'idx_tgr_group_result_status',
    'idx_tgr_group_has_history',
    'idx_dsr_identifier_service_key',
    'idx_tghr_group_cid_service',
    'idx_tghr_group_name_service',
    'idx_person_master_canonical_key',
    'idx_person_master_cid',
    'idx_person_identifiers_person_id',
    'idx_person_identifiers_value',
    'idx_dse_person_id',
    'idx_dse_person_service',
    'idx_tgm_person_id',
    'idx_tgm_group_job_id'
  )
ORDER BY indexname;

-- Phase D columns on target_group_results
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'target_group_results'
  AND column_name IN (
    'canonical_person_key',
    'person_link_status',
    'review_required',
    'link_confidence_score',
    'person_link_notes'
  )
ORDER BY column_name;
SQL

echo "  → schema check complete."

# ── 5. Re-generate results via the backend ────────────────────────────────────
echo ""
echo "[5/7] Re-generating results for all existing target groups..."
echo "      (calls POST /api/target-groups/{id}/generate-results for each job)"
echo ""

# Start the backend in background if not running
BACKEND_UP=false
if curl -sf http://127.0.0.1:8010/api/system/status > /dev/null 2>&1; then
  echo "  Backend already running at :8010"
  BACKEND_UP=true
else
  echo "  Starting backend temporarily..."
  uvicorn app.main:app --host 127.0.0.1 --port 8010 &
  BACKEND_PID=$!
  sleep 3
  BACKEND_UP=true
fi

# Find all group_job_ids and regenerate
GROUP_IDS=$(psql "${PSQL_URL}" -t -A -c "SELECT id FROM target_group_jobs ORDER BY created_at;")

if [ -z "$GROUP_IDS" ]; then
  echo "  No target group jobs found — skipping regeneration."
else
  for gid in $GROUP_IDS; do
    echo "  Regenerating group: $gid"
    HTTP_CODE=$(curl -s -o /tmp/regen_response.json -w "%{http_code}" \
      -X POST "http://127.0.0.1:8010/api/target-groups/${gid}/generate-results" \
      -H "Content-Type: application/json")
    if [ "$HTTP_CODE" = "200" ]; then
      TOTAL=$(python3 -c "import json,sys; d=json.load(open('/tmp/regen_response.json')); print(d.get('summary',{}).get('total_target_people','?'))" 2>/dev/null || echo "?")
      COVERAGE=$(python3 -c "import json,sys; d=json.load(open('/tmp/regen_response.json')); print(d.get('summary',{}).get('coverage_percent','?'))" 2>/dev/null || echo "?")
      echo "    ✓ HTTP $HTTP_CODE | total=$TOTAL | coverage=$COVERAGE%"
    else
      echo "    ✗ HTTP $HTTP_CODE"
      cat /tmp/regen_response.json
    fi
  done
fi

# Stop the backend if we started it
if [ -n "${BACKEND_PID:-}" ]; then
  kill "$BACKEND_PID" 2>/dev/null || true
  echo "  Backend stopped."
fi

echo "  → regeneration complete."

# ── 6. Verify data in DB ─────────────────────────────────────────────────────
echo ""
echo "[6/7] Verifying data in DB..."
psql "${PSQL_URL}" <<'SQL'
-- Summary cache rows created
SELECT
  COUNT(*) AS summary_cache_rows,
  COUNT(DISTINCT group_job_id) AS groups_covered
FROM target_group_result_summaries;

-- Phase D fields on results
SELECT
  COUNT(*) AS total_results,
  COUNT(CASE WHEN canonical_person_key IS NOT NULL THEN 1 END) AS with_canonical_key,
  COUNT(CASE WHEN review_required = TRUE THEN 1 END) AS review_required_count,
  COUNT(CASE WHEN person_link_status IS NOT NULL THEN 1 END) AS with_link_status
FROM target_group_results;

-- 1-person-1-row check: each target_row_id appears at most once per job
SELECT
  COUNT(*) AS duplicate_target_row_ids
FROM (
  SELECT target_row_id, group_job_id, COUNT(*) AS cnt
  FROM target_group_results
  WHERE target_row_id IS NOT NULL
  GROUP BY target_row_id, group_job_id
  HAVING COUNT(*) > 1
) sub;
-- Expected: 0

-- result_status distribution
SELECT result_status, COUNT(*) AS count
FROM target_group_results
GROUP BY result_status
ORDER BY count DESC;

-- Two-source history: rows using target-group-file history (source = 'target_group_file')
SELECT
  latest_relevant_source_type,
  COUNT(*) AS count
FROM target_group_results
WHERE latest_relevant_source_type IS NOT NULL
GROUP BY latest_relevant_source_type
ORDER BY count DESC;

-- Summary cache sanity: totals should equal sum of parts
SELECT
  g.id AS group_id,
  s.total_target_people,
  (s.valid_identifier_people
    + s.invalid_identifier_people
    + s.non_thai_nationality_people
    + s.insufficient_identity_people
    + s.outside_target_scope_people
    + s.review_required_identity_people) AS parts_sum,
  s.coverage_percent
FROM target_group_result_summaries s
JOIN target_group_jobs g ON g.id = s.group_job_id
ORDER BY s.generated_at DESC;
SQL

echo "  → data verification complete."

echo ""
echo "[7/7] Done. Review the output above for:"
echo "  - All 5 new tables present"
echo "  - All 14 new indexes present"
echo "  - Phase D columns present on target_group_results"
echo "  - summary_cache_rows > 0"
echo "  - with_canonical_key = total_results (every row has a canonical key)"
echo "  - duplicate_target_row_ids = 0 (1-person-1-row)"
echo "  - parts_sum = total_target_people in each summary row"
echo "============================================================"
