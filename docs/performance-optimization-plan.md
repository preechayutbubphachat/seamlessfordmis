# Performance Optimization Plan

## Optimizations Applied In This Round

### 1. Server-Side Pagination For Person-Level Results

Changed:

- `/api/target-groups/{group_id}/results` now accepts `page` and `page_size`
- backend returns only the requested page of rows
- response includes:
  - `page`
  - `page_size`
  - `total_filtered_rows`
  - `total_pages`

Reason:

- removes the biggest bottleneck: returning all result rows in one response

Measured impact:

- before: ~18.5 MB payload, ~29-35s
- after: ~134 KB payload for page 1, ~4.2-5.8s

### 2. Server-Side Filter And Search

Changed:

- backend results endpoint now supports:
  - `view`
  - `query`
  - `overdue_enabled`
  - `overdue_years`
- frontend no longer needs to filter 19,960 rows in memory

Reason:

- keeps filter/search cost close to database query scope
- avoids expensive client-side full-list recalculation

### 3. Debounced Search In Results Workspace

Changed:

- frontend search updates URL/filter state after a short debounce

Reason:

- prevents firing an API request on every keystroke
- keeps state persistence via URL without excessive churn

### 4. Lazy Detail Loading Kept For Modal

Changed:

- patient detail modal still fetches detail on open only
- added extra patient context from target group source data already stored in `raw_json`

Reason:

- avoids loading per-patient detail for every row upfront

## Current Read Path After Optimization

1. page loads target group detail shell
2. frontend requests one page of results only
3. filters/search update query params
4. backend returns only filtered/paged rows
5. patient detail modal loads extra history only when user opens a row

## Why We Did Not Apply Every Possible Optimization

These were intentionally not forced in this round:

- full table virtualization
- background job queue redesign
- full summary caching layer
- materialized result summary tables
- broad schema migration to new linked model

Reason:

- biggest bottleneck was already identifiable and fixable without a risky architecture rewrite
- production-safe incremental change was preferred

## Remaining Hotspots

### Results Endpoint Still 4-6 Seconds

Current likely causes:

- summary and breakdown are still recomputed from the whole result snapshot
- backend still loads all result rows for summary building before slicing the requested page

Recommended next optimization:

1. split summary query from row query with aggregate SQL
2. avoid loading all `TargetGroupResult` rows into memory for every paged request
3. optionally cache summary per `group_id + selected_service_hash + overdue_years`

### Result Summary API Still Around 0.8-1.2 Seconds

Recommended next optimization:

- move summary math into aggregate SQL instead of Python iteration over all rows

## Practical Next Steps

1. optimize `ResultGenerationService.get_results()` to use aggregate SQL for summary
2. add dedicated indexes for `target_group_results` read patterns if migration path is ready
3. consider a lightweight cached summary table for heavy groups
4. keep patient modal lazy-loaded
5. evaluate pagination size 50 vs 100 for staff workflow if scrolling still feels heavy


---

## Phase E Optimizations Applied (2026-05-04)

### 5. Aggregate SQL Summary (replaces Python iteration)

Changed:

- `_build_summary_from_sql()` replaces `_build_summary()` for all read paths
- uses a single `SELECT` with `func.sum(case(...))` CASE expressions — one DB round-trip
- `get_result_summary()` and `get_results()` both use this path

Reason:

- `_build_summary()` loaded all `TargetGroupResult` rows into Python and iterated — O(N) memory and
  CPU per request even after pagination fixed the payload size bottleneck
- SQL aggregation pushes the math into PostgreSQL and returns only one scalar row

### 6. Summary Cache Table (`target_group_result_summaries`)

Changed:

- `generate()` writes summary to `target_group_result_summaries` via
  `INSERT ... ON CONFLICT DO UPDATE`
- `get_result_summary()` tries the cache first (single primary-key lookup) before falling back to
  aggregate SQL
- migration 0012 creates the table with a unique index on `(group_job_id, selected_service_hash)`

Reason:

- even aggregate SQL adds latency proportional to the number of result rows
- the cache reduces summary endpoint cost to effectively O(1) for already-generated groups

### 7. Page-Scoped Context Rebuild in `get_results()`

Changed:

- replaced `all_target_rows` full-table load + `_build_person_contexts()` with a targeted
  `SELECT ... WHERE id IN (page_target_row_ids)` loading only the primary rows for the current page
- Phase D stored fields (`person_link_status`, `review_required`, `duplicate_reason`) are read
  directly from `TargetGroupResult` — no fallback recomputation needed for Phase D results
- walrus operator `:=` in the results comprehension avoids computing `page_rows` twice per result

Reason:

- the full-table context rebuild was the dominant latency source after pagination was fixed
- O(page_size) queries instead of O(total_rows) queries per paged request

### 8. Performance Indexes (migration 0013)

Changed:

- five new composite indexes on hot read paths (see performance-diagnosis.md Phase E section)
- four linked-model scaffold tables added as empty schema (person_master, person_identifiers,
  disease_screening_events, target_group_membership)

Reason:

- composite indexes allow PostgreSQL to satisfy multi-column WHERE clauses with a single index scan
- scaffold tables establish the FK graph for the future linked model migration (Phase F / issue #9)

## Updated Status After Phase E

| Path | Before Phase E | After Phase E |
|---|---|---|
| `GET /result-summary` | ~0.8-1.2 s | ~sub-50 ms (cache hit) |
| `GET /results` summary build | ~4-6 s | O(1) cache + O(page_size) row fetch |
| `GET /results` context rebuild | O(N_total) rows | O(page_size) rows |
| Filter/view queries | full scan | index-covered |
