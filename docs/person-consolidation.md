# Person-Level Consolidation (Phase D)

## Goal

The final visible result table is person-centered: **one person = one visible row**.

Multiple source rows for the same person are grouped into a single
`PersonResultContext` during result generation. All supporting evidence is
preserved in provenance details for modal/detail display.

---

## Grouping Key Strategy

Each set of source rows is assigned a `canonical_person_key` that determines
which rows belong to the same logical person.

The key is chosen in this priority order:

| Priority | Condition | Key format |
|---|---|---|
| 1 | Row already linked by patient matching service | `identifier:<matched_identifier_basis>` |
| 2 | Valid 13-digit CID present | `cid:<normalized_cid>` |
| 3 | Full name + exact birth date present | `name_birth:<name>:<dob>` |
| 4 | Full name + address (review-required) | `review_name_address:<name>:<addr>` |
| 5 | Full name only (review-required) | `review_name:<name>` |
| 6 | No usable identity | `row:<uuid>` (one context per row) |

The `canonical_person_key` is stored on `TargetGroupResult` so
`get_results()` can look up the right context without recomputing row order
across calls.

---

## Identity Resolution Order

Implemented in `_person_link_details()` and surfaced as `person_link_status`:

### High confidence (review_required = false)

| Status | Rule |
|---|---|
| `citizen_id_exact` | At least one row in the group has a valid 13-digit CID |
| `name_birthdate_exact` | All rows share exact normalized full name + exact birth date |

### Acceptable but uncertain (review_required = true)

| Status | Rule |
|---|---|
| `name_birthdate_address_secondary` | Name present; address used as supporting evidence but no birth date |
| `review_required` | Name present but neither birth date nor address is available |
| `insufficient_identity_data` | Not enough identity data to link safely |

### Address-only rule

Address is **never** the sole merge criterion. Two rows with the same address
but different names always produce two separate contexts. Address only helps
confirm an existing name-based tentative match.

---

## Why Provenance Is Separated from Visible Rows

Before consolidation, the same physical person could appear as multiple rows in
the result table because:

- the target-group file contained duplicate roster rows
- the same person appeared in multiple sheets (roster + history)
- multiple evidence events existed for a single person

Phase D groups all such rows under one visible person result. The individual
source rows are preserved in `provenance_details[]` so auditors can inspect:

- which file/sheet/row each source entry came from
- the match method applied to each row
- any per-row warnings or errors

The main table remains compact; detail is available in the patient detail modal.

---

## Stored Fields (Phase D additions to TargetGroupResult)

| Column | Type | Description |
|---|---|---|
| `canonical_person_key` | Text | Grouping key from `_person_group_key()` |
| `person_link_status` | String(40) | Identity resolution outcome |
| `review_required` | Boolean | True when confidence is insufficient for auto-merge |
| `duplicate_reason` | Text | Human-readable merge explanation |

These columns are nullable for backward compatibility. Rows generated before
the Phase D migration will have NULL values and fall back to recomputation
at query time.

---

## Context Lookup Fix

Before Phase D, `get_results()` resolved provenance by:

```python
contexts_by_primary_id[result.target_row_id]
```

This was fragile: if the sort order of `_build_person_contexts()` produced a
different "primary row" at query time than at generate time, the lookup would
miss and return empty provenance.

After Phase D, the lookup uses the stored canonical key first:

```python
# Preferred: stable across calls
if result.canonical_person_key in contexts_by_key:
    return contexts_by_key[result.canonical_person_key].rows
# Fallback: for results generated before Phase D migration
if result.target_row_id in contexts_by_primary_id:
    return contexts_by_primary_id[result.target_row_id].rows
return []
```

---

## DB-Level Filtering

Storing `review_required` and `person_link_status` enables new DB-level filters
without loading all target_group_rows on every request:

```
GET /api/target-groups/{group_id}/results?view=review_required
```

Returns only rows where `review_required = true` — persons whose identity
merge is uncertain and needs human verification.

---

## Current Limitations

1. Name-based matching uses exact normalized strings only. Typos, nickname
   variants, or transliteration differences are not fuzzy-matched.
2. `review_name_address` grouping uses exact address string equality after
   normalization. Partial address matches are not supported.
3. Rows generated before the Phase D migration have NULL `canonical_person_key`
   and fall back to the fragile `target_row_id` lookup until re-generated.
4. The `row:<uuid>` fallback key (no usable identity) means truly anonymous
   rows are never merged with any other row — correct but unhelpful for
   de-identification scenarios.
5. Frontend modal wiring for the `/source-history` endpoint and
   `review_required` badge remains an open item (issue #6).

---

## Tests (L.1–L.8)

File: `backend/tests/test_person_consolidation.py`

| ID | Description |
|---|---|
| L.1 | Duplicate CID rows consolidate into exactly one PersonResultContext |
| L.2 | Same person across multiple sheets consolidates correctly |
| L.3 | Multiple evidence rows stay as one context (count grows, not rows) |
| L.4 | CID exact match wins over name-only key |
| L.5 | Name + birth-date fallback works when CID is missing |
| L.6 | Address-only evidence does not silently merge distinct people |
| L.7 | Uncertain identity cases produce review_required person_link_status |
| L.8 | Provenance count reflects all grouped rows, not just primary |

---

## Implementation Files

| File | Change |
|---|---|
| `backend/app/models/target_group_result.py` | Added `canonical_person_key`, `person_link_status`, `review_required`, `duplicate_reason` columns |
| `backend/alembic/versions/20260503_0011_phase_d_person_link_fields.py` | Migration: ADD COLUMN x4 + 3 composite indexes |
| `backend/app/services/result_generation_service.py` | Store new fields in `generate()`, use `_resolve_context_rows()` in `get_results()`, add `review_required` view filter |
| `backend/app/schemas/result.py` | Added `canonical_person_key` field to `GroupResultRowResponse` |
| `backend/tests/test_person_consolidation.py` | Tests L.1–L.8 |
