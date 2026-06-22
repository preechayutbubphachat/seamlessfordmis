# Result Output Model

## Summary Fields

- `group_job_id`
- `selected_service_keys`
- `overdue_threshold_years`
- `total_target_people`
- `valid_identifier_people`
- `invalid_identifier_people`
- `non_thai_nationality_people`
- `insufficient_identity_people`
- `outside_target_scope_people`
- `review_required_identity_people`
- `people_with_selected_history`
- `people_without_selected_history`
- `never_checked_people`
- `checked_but_overdue_people`
- `checked_and_within_threshold_people`
- `coverage_percent`
- `coverage_denominator`
- `coverage_denominator_people`
- `generated_at`

## Coverage Formula

```text
coverage_percent = (people_with_selected_history / valid_identifier_people) * 100
```

`valid_identifier_people` now excludes rows that should not participate in ordinary screening coverage:

- invalid identifier
- missing identifier without safe fallback identity
- non-Thai nationality
- outside target scope
- insufficient identity data
- review-required identity rows

## Person-level Result Row

- `result_id`
- `target_row_id`
- `group_job_id`
- `normalized_cid`
- `matched_identifier`
- `matched_name_basis`
- `full_name`
- `age`
- `raw_age`
- `birth_date`
- `sex`
- `match_status`
- `match_method`
- `match_confidence`
- `person_link_status` — `citizen_id_exact` | `name_birthdate_exact` | `name_birthdate_address_secondary` | `review_required` | `insufficient_identity_data`
- `duplicate_reason`
- `canonical_person_key` — Phase D: stable grouping key stored on the result; used by `get_results()` for context lookup
- `review_required`
- `result_category`
- `result_status`
- `screening_status`
- `has_selected_service`
- `matching_record_count`
- `matched_service_keys`
- `last_visit_date`
- `days_since_last_visit`
- `years_since_last_visit`
- `history_found_in_screening_db`
- `history_found_in_target_group_file`
- `history_source_summary` — one of: `screening_db_only` | `target_group_file_only` | `both_sources` | `no_history_found`
- `last_relevant_source`
- `latest_relevant_source_type` — Phase C: explicit source type for the latest qualifying date. Values: `"screening_db"` | `"target_group_file"` | `null`. Mirrors `last_relevant_source`; added under the Phase C spec name.
- `latest_source_file_name`
- `latest_source_sheet_name`
- `latest_source_row_no`
- `target_group_nationality`
- `target_group_address`
- `source_file_id`
- `source_file_name`
- `source_sheet_name`
- `source_row_no`
- `provenance_summary_count`
- `provenance_details`
- `target_group_history_events`
- `warning_message`

## Result Categories

- `screening_db_only`
- `target_group_file_only`
- `both_sources`
- `no_history_found`
- `invalid_identifier`
- `missing_identifier`
- `review_required_identity`
- `insufficient_identity_data`
- `non_thai_nationality`
- `outside_target_scope`
- `needs_review`

## Provenance Rules
