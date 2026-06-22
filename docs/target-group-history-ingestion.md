# Target Group History Ingestion

## Scope

Target group Excel uploads are no longer treated as roster-only files.
The importer now inspects every sheet and keeps two evidence paths separate:

1. `roster_sheet`
2. `history_sheet`
3. `mixed_sheet`
4. `unknown_sheet`

The disease screening database remains the primary formal source, but target-group-side history is now a valid secondary evidence source in result generation.

## Sheet Classification

The importer classifies a sheet by combining:

- sheet name hints
- person-identifying columns such as `CID`, `citizen_id`, `full_name`
- history-oriented columns such as `visit_date`, `ICD10`, `HPV`, `result`, `hospital_name`, `doctor_name`, `note`
- support columns such as `birth_date`, `nationality`, `address`

If a sheet contains person columns plus history/service columns, it is treated as `history_sheet`.
If a sheet contains both target roster context and medical history context in the same rows, it is treated as `mixed_sheet`.
If the meaning is unclear, the sheet is left as `unknown_sheet` and surfaced for review instead of being silently merged.

## Stored Evidence

Sheet metadata is stored in `target_group_sheets` with:

- `source_file_id`
- `sheet_name`
- `sheet_index`
- `sheet_type`
- `row_count`
- `column_names_json`
- `classification_confidence`
- `notes`

History rows are stored in `target_group_history_rows` with provenance:

- `source_file_name`
- `source_sheet_id`
- `source_sheet_name`
- `source_row_no`
- raw and normalized identity values
- raw and normalized birth date / address
- raw and normalized service/date values
- raw result / HPV / hospital / doctor / note
- full `raw_json` payload for review

Roster rows may also contain embedded service history fields.
Those are staged as derived history rows only for `roster_sheet`.
`mixed_sheet` rows already stage history directly and are not duplicated through an extra embedded-history pass.

## Result Logic

Result generation now checks history in this order:

1. disease screening database
2. target group history sheets and embedded roster history
3. otherwise `no_history_found`

If the database has no history but the target group file has valid history for the person, the person must not be classified as `ยังไม่พบประวัติ`.

## Provenance Rules

History evidence keeps source distinction visible:

- `screening_db_only`
- `target_group_file_only`
- `both_sources`
- `no_history_found`

The latest relevant date is taken from the union of eligible records across both sources, but the response also records which source contributed that latest date.
