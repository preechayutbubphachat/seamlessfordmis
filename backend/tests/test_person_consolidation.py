"""
L.1 – L.8  Phase D: Person-level consolidation and identity resolution tests

All tests exercise pure-logic helpers in ResultGenerationService without
a live database. They use SimpleNamespace to simulate TargetGroupRow objects
with only the fields that the grouping/linking helpers inspect.
"""
from datetime import date
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.services.result_generation_service import ResultGenerationService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _row(
    cid: str | None = None,
    cid_status: str = "valid_identifier",
    full_name: str | None = None,
    birth_date: date | None = None,
    address: str | None = None,
    match_status: str = "matched",
    matched_identifier_basis: str | None = None,
    source_row_no: int = 1,
    row_no: int = 1,
):
    """Minimal TargetGroupRow-like object for grouping tests."""
    return SimpleNamespace(
        id=uuid4(),
        normalized_cid=cid,
        cid_validation_status=cid_status if cid else "missing_identifier",
        normalized_full_name=full_name,
        normalized_birth_date=birth_date,
        raw_json={"address": address} if address else {},
        match_status=match_status,
        matched_identifier_basis=matched_identifier_basis,
        matched_patient_id=None,
        source_row_no=source_row_no,
        row_no=row_no,
        error_message=None,
        warning_message=None,
        raw_full_name=full_name,
        normalized_age=None,
        normalized_sex=None,
        raw_age=None,
        raw_target_history_labels=None,
        raw_target_history_note=None,
        normalized_target_history_last_visit_date=None,
        normalized_target_history_service_keys=None,
        source_file_name=None,
        source_file_id=None,
        confidence_flag=None,
        matched_name_basis=None,
        created_at=None,
    )


# ---------------------------------------------------------------------------
# L.1  Duplicate CID rows consolidate into exactly one visible result row
# ---------------------------------------------------------------------------

def test_l1_duplicate_cid_rows_consolidate():
    """Two roster rows with the same valid CID must produce one PersonResultContext."""
    cid = "1234567890123"
    row1 = _row(cid=cid, source_row_no=1)
    row2 = _row(cid=cid, source_row_no=2)

    contexts = ResultGenerationService._build_person_contexts([row1, row2])

    assert len(contexts) == 1, "duplicate CID rows must produce exactly one context"
    ctx = contexts[0]
    assert ctx.key.startswith("cid:")
    assert len(ctx.rows) == 2
    assert ctx.primary_row in (row1, row2)


# ---------------------------------------------------------------------------
# L.2  Same person across multiple sheets consolidates correctly
# ---------------------------------------------------------------------------

def test_l2_same_person_multi_sheet_consolidates():
    """Same CID from two different sheets (source_row_no differ) = one context."""
    cid = "9876543210987"
    row_sheet_a = _row(cid=cid, source_row_no=5)
    row_sheet_b = _row(cid=cid, source_row_no=10)

    contexts = ResultGenerationService._build_person_contexts([row_sheet_a, row_sheet_b])

    assert len(contexts) == 1
    assert len(contexts[0].rows) == 2


# ---------------------------------------------------------------------------
# L.3  Multiple history/evidence rows stay as one result (count increases, not rows)
# ---------------------------------------------------------------------------

def test_l3_multi_evidence_rows_one_result_context():
    """Three rows same CID -> one context; grouped rows count = 3."""
    cid = "1111111111111"
    rows = [_row(cid=cid, source_row_no=i) for i in range(3)]

    contexts = ResultGenerationService._build_person_contexts(rows)

    assert len(contexts) == 1
    assert len(contexts[0].rows) == 3


# ---------------------------------------------------------------------------
# L.4  CID exact match wins over name-only key
# ---------------------------------------------------------------------------

def test_l4_cid_wins_over_name_fallback():
    """A row with valid CID groups under cid: key, not name: key."""
    cid = "2222222222222"
    row = _row(cid=cid, full_name="นางสาว ก")

    key = ResultGenerationService._person_group_key(row)

    assert key.startswith("cid:"), f"expected cid: key, got {key!r}"
    assert cid in key


# ---------------------------------------------------------------------------
# L.5  Name + birth-date fallback works when CID is missing
# ---------------------------------------------------------------------------

def test_l5_name_birthdate_fallback():
    """Two rows without CID but same name+birthdate -> same group key."""
    name = "นางสาว ข"
    dob = date(1990, 5, 15)
    row1 = _row(cid=None, cid_status="missing_identifier", full_name=name, birth_date=dob)
    row2 = _row(cid=None, cid_status="missing_identifier", full_name=name, birth_date=dob)

    key1 = ResultGenerationService._person_group_key(row1)
    key2 = ResultGenerationService._person_group_key(row2)

    assert key1 == key2
    assert key1.startswith("name_birth:")

    contexts = ResultGenerationService._build_person_contexts([row1, row2])
    assert len(contexts) == 1


# ---------------------------------------------------------------------------
# L.6  Address-only evidence does not silently merge distinct people
# ---------------------------------------------------------------------------

def test_l6_address_only_does_not_merge_distinct_people():
    """Two rows with different names but same address must NOT merge."""
    addr = "123 ถนนตัวอย่าง"
    row1 = _row(cid=None, cid_status="missing_identifier", full_name="นางสาว ค", address=addr)
    row2 = _row(cid=None, cid_status="missing_identifier", full_name="นาง ง", address=addr)

    key1 = ResultGenerationService._person_group_key(row1)
    key2 = ResultGenerationService._person_group_key(row2)

    # Different names -> different keys despite same address
    assert key1 != key2

    contexts = ResultGenerationService._build_person_contexts([row1, row2])
    assert len(contexts) == 2, "distinct names must produce separate person contexts"


# ---------------------------------------------------------------------------
# L.7  Uncertain identity cases produce review_required person_link_status
# ---------------------------------------------------------------------------

def test_l7_uncertain_identity_is_review_required():
    """Name-only row (no CID, no birth date, no address) -> review_required link."""
    row = _row(cid=None, cid_status="missing_identifier", full_name="นาย จ")

    link_status, reason, review_flag = ResultGenerationService._person_link_details([row])

    assert review_flag is True
    assert link_status in {"review_required", "insufficient_identity_data"}


# ---------------------------------------------------------------------------
# L.8  Provenance count reflects all grouped rows, not just primary
# ---------------------------------------------------------------------------

def test_l8_provenance_count_reflects_grouped_rows():
    """After grouping 4 rows under the same CID, the context has 4 rows in .rows."""
    cid = "3333333333333"
    rows = [_row(cid=cid, source_row_no=i) for i in range(1, 5)]

    contexts = ResultGenerationService._build_person_contexts(rows)

    assert len(contexts) == 1
    ctx = contexts[0]
    # All 4 rows are preserved for provenance
    assert len(ctx.rows) == 4
    # Primary is the best-ranked row (they are all equal rank, so any is fine)
    assert ctx.primary_row in ctx.rows
