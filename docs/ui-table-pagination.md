# UI Table Pagination

## Controls

The target group results table now supports:

- category tabs
- text search
- overdue filter toggle plus custom year input
- rows-per-page selector
- guarded `ทั้งหมด` mode for smaller filtered result sets

## Rows Per Page

Supported page sizes:

- 10
- 25
- 50
- 100
- 250

The current page resets to page 1 whenever the active filters or page size change.

## Show All Guard

`ทั้งหมด` is intentionally guarded for performance.

- The UI enables `ทั้งหมด` only when the current filtered result set is at most 1,000 rows.
- This prevents the browser from rendering very large result sets at once and keeps scrolling responsive.

## Filter Summary

The table header shows:

- how many rows match the current filters
- what percent of the total target group that represents
- how many rows remain outside the current filtered set
- the currently displayed row range

The denominator for this local UI summary is always `total_target_people` for the selected result set.
