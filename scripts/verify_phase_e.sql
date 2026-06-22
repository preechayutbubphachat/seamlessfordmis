-- =============================================================================
-- verify_phase_e.sql
-- Run after `alembic upgrade head` to verify Phase E schema + data.
-- Usage: psql $DATABASE_URL -f scripts/verify_phase_e.sql
-- =============================================================================

\echo '=== [1] New Phase E tables ==='
SELECT tablename, 'PRESENT' AS status
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

\echo ''
\echo '=== [2] New Phase E indexes ==='
SELECT indexname, tablename
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

\echo ''
\echo '=== [3] Phase D columns on target_group_results ==='
SELECT column_name, data_type, is_nullable
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

\echo ''
\echo '=== [4] Summary cache rows (after regenerate) ==='
SELECT
  COUNT(*) AS total_summary_rows,
  COUNT(DISTINCT group_job_id) AS groups_covered
FROM target_group_result_summaries;

\echo ''
\echo '=== [5] Phase D field coverage on result rows ==='
SELECT
  COUNT(*)                                                           AS total_results,
  COUNT(CASE WHEN canonical_person_key IS NOT NULL THEN 1 END)      AS with_canonical_key,
  COUNT(CASE WHEN person_link_status IS NOT NULL THEN 1 END)        AS with_link_status,
  COUNT(CASE WHEN review_required = TRUE THEN 1 END)                AS review_required_count
FROM target_group_results;

\echo ''
\echo '=== [6] 1-person-1-row check (expect: 0 duplicates) ==='
SELECT COUNT(*) AS duplicate_target_row_ids
FROM (
  SELECT target_row_id, group_job_id, COUNT(*) AS cnt
  FROM target_group_results
  WHERE target_row_id IS NOT NULL
  GROUP BY target_row_id, group_job_id
  HAVING COUNT(*) > 1
) sub;

\echo ''
\echo '=== [7] result_status distribution ==='
SELECT result_status, COUNT(*) AS count
FROM target_group_results
GROUP BY result_status
ORDER BY count DESC;

\echo ''
\echo '=== [8] Two-source history coverage ==='
SELECT
  latest_relevant_source_type,
  COUNT(*) AS count
FROM target_group_results
WHERE latest_relevant_source_type IS NOT NULL
GROUP BY latest_relevant_source_type
ORDER BY count DESC;

\echo ''
\echo '=== [9] Summary cache integrity (parts_sum should = total_target_people) ==='
SELECT
  LEFT(CAST(group_job_id AS text), 8) || '...' AS group_id_prefix,
  total_target_people,
  (valid_identifier_people
     + invalid_identifier_people
     + non_thai_nationality_people
     + insufficient_identity_people
     + outside_target_scope_people
     + review_required_identity_people) AS parts_sum,
  total_target_people - (
    valid_identifier_people
     + invalid_identifier_people
     + non_thai_nationality_people
     + insufficient_identity_people
     + outside_target_scope_people
     + review_required_identity_people
  ) AS diff,
  coverage_percent,
  generated_at
FROM target_group_result_summaries
ORDER BY generated_at DESC;

\echo ''
\echo '=== [10] History coverage breakdown from summary cache ==='
SELECT
  LEFT(CAST(group_job_id AS text), 8) || '...' AS group_id_prefix,
  people_with_selected_history,
  people_without_selected_history,
  never_checked_people,
  checked_but_overdue_people,
  checked_and_within_threshold_people
FROM target_group_result_summaries
ORDER BY generated_at DESC;

\echo ''
\echo '=== Phase E verification complete ==='
\echo 'Expected results:'
\echo '  [1] 5 tables present'
\echo '  [2] 14 indexes present'
\echo '  [3] 5 Phase D columns present'
\echo '  [4] summary rows > 0 (after regenerate)'
\echo '  [5] with_canonical_key = total_results'
\echo '  [6] duplicate_target_row_ids = 0'
\echo '  [9] diff = 0 for every group (parts sum = total)'
