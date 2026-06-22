# Identity Resolution Rules

## Matching Order

The current conservative same-person logic uses this order:

1. exact valid 13-digit citizen ID
2. exact normalized full name plus exact birth date
3. exact normalized full name plus matching address as supporting evidence only
4. otherwise keep the row reviewable instead of silently merging

Address never merges rows by itself.
Name-only matches are not treated as high-confidence identity merges.

## Person Link Status

Person-level grouped results expose a review-oriented link status:

- `citizen_id_exact`
- `name_birthdate_exact`
- `name_birthdate_address_secondary`
- `review_required`
- `insufficient_identity_data`

These describe how duplicate roster rows or multi-sheet rows were consolidated into one visible person result.

## Review vs Auto-Merge

High confidence:

- exact valid citizen ID
- exact normalized full name plus exact birth date

Review required:

- name plus address only
- name present but birth date missing or ambiguous
- insufficient identity detail to merge confidently

## Target Scope Separation

The result layer now separates people who should not be treated as ordinary screening candidates:

- `non_thai_nationality`
- `outside_target_scope`
- `insufficient_identity_data`
- `review_required_identity`

These categories are excluded from ordinary no-history coverage calculations.


## Stored Fields (Phase D)

After Phase D, identity resolution outcomes are stored on `TargetGroupResult`
rather than being recomputed on every read:

| Field | Values |
|---|---|
| `canonical_person_key` | Grouping key: `cid:<cid>` \| `name_birth:<name>:<dob>` \| `review_name_address:<name>:<addr>` \| `review_name:<name>` \| `row:<id>` |
| `person_link_status` | `citizen_id_exact` \| `name_birthdate_exact` \| `name_birthdate_address_secondary` \| `review_required` \| `insufficient_identity_data` |
| `review_required` | `true` when confidence is not sufficient for auto-merge |
| `duplicate_reason` | Human-readable explanation of how rows were merged |

These fields enable DB-level filtering (e.g., `?view=review_required`) without
loading all source rows on every request.

Rows generated before the Phase D migration have NULL values and fall back to
recomputation at query time until re-generated.
