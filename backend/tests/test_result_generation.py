"""
K.1 – K.7  Two-source result generation tests (Phase C)

These tests exercise _build_row_result_payload() and related helpers
without a live database. They use plain dataclasses / SimpleNamespace to
simulate DiseaseScreeningRecord and TargetGroupHistoryEvidence objects.
"""
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.services.result_generation_service import (
    ResultGenerationService,
    TargetGroupHistoryEvidence,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _screening_record(visit_date: date, service_key: str = "cervical_screen"):
    """Minimal DiseaseScreeningRecord-like object."""
    return SimpleNamespace(
        id=uuid4(),
        source_import_job_id=uuid4(),
        source_file_id=uuid4(),
        source_row_no=1,
        normalized_person_identifier="1111111111111",
        normalized_service_key=service_key,
        visit_date=visit_date,
        transaction_id=None,
    )


def _tg_evidence(
    visit_date: date | None,
    service_key: str = "cervical_screen",
    cid: str = "1111111111111",
) -> TargetGroupHistoryEvidence:
    return TargetGroupHistoryEvidence(
        source_type="target_group_history_sheet",
        source_file_name="target.xlsx",
        source_sheet_name="ประวัติ",
        source_row_no=3,
        normalized_cid=cid,
        normalized_full_name="นางสาว ก",
        normalized_birth_date=None,
        normalized_address=None,
        raw_nationality=None,
        raw_service_type="คัดกรองมะเร็งปากมดลูก",
        normalized_service_key=service_key,
        normalized_visit_date=visit_date,
        raw_result="Negative",
        raw_hospital="รพ.ตัวอย่าง",
        raw_doctor=None,
        raw_note=None,
        warning_message=None,
    )


def _roster_row(**overrides):
    from app.models.target_group_row import TargetGroupRow
    defaults = dict(
        group_job_id=uuid4(),
        source_file_id=uuid4(),
        source_file_name="target.xlsx",
        row_no=2,
        source_row_no=2,
        raw_cid="1111111111111",
        normalized_cid="1111111111111",
        cid_validation_status="valid_identifier",
        normalized_full_name="นางสาว ก",
        raw_full_name="นางสาว ก",
        normalized_age=35,
        normalized_sex="female",
        parse_status="parsed",
        validation_status="valid",
        duplicate_status="unique_in_job",
        match_status="matched",
    )
    defaults.update(overrides)
    return TargetGroupRow(**defaults)


def _record_key_map(key: str = "cervical_screen") -> dict:
    return {key: {key}}


# ---------------------------------------------------------------------------
# K.1 – screening DB only → result_category = screening_db_only
# ---------------------------------------------------------------------------
def test_k1_screening_db_only():
    row = _roster_row()
    eligible_records = [_screening_record(date(2024, 6, 1))]
    eligible_history = []
    payload = ResultGenerationService._build_row_result_payload(
        row, eligible_records, eligible_history, _record_key_map()
    )
    assert payload["has_selected_service"] is True
    assert payload["result_status"] == "screening_db_only"
    assert payload["last_visit_date"] == date(2024, 6, 1)
    assert payload["matching_record_count"] == 1


# ---------------------------------------------------------------------------
# K.2 – TG file only → result_category = target_group_file_only, has_history
# ---------------------------------------------------------------------------
def test_k2_target_group_file_only_not_classified_as_no_history():
    row = _roster_row()
    eligible_records = []
    eligible_history = [_tg_evidence(date(2023, 9, 15))]
    payload = ResultGenerationService._build_row_result_payload(
        row, eligible_records, eligible_history, _record_key_map()
    )
    assert payload["has_selected_service"] is True, \
        "person with TG-file history must not be classified as no-history"
    assert payload["result_status"] == "target_group_file_only"
    assert payload["last_visit_date"] == date(2023, 9, 15)
    assert payload["matching_record_count"] == 1


# ---------------------------------------------------------------------------
# K.3 – both sources → result_category = both_sources
# ---------------------------------------------------------------------------
def test_k3_both_sources():
    row = _roster_row()
    eligible_records = [_screening_record(date(2024, 3, 10))]
    eligible_history = [_tg_evidence(date(2023, 9, 15))]
    payload = ResultGenerationService._build_row_result_payload(
        row, eligible_records, eligible_history, _record_key_map()
    )
    assert payload["result_status"] == "both_sources"
    assert payload["has_selected_service"] is True
    assert payload["matching_record_count"] == 2


# ---------------------------------------------------------------------------
# K.4 – neither source → result_category = no_history_found
# ---------------------------------------------------------------------------
def test_k4_no_history_in_either_source():
    row = _roster_row()
    payload = ResultGenerationService._build_row_result_payload(
        row, [], [], _record_key_map()
    )
    assert payload["has_selected_service"] is False
    assert payload["result_status"] == "no_history_found"
    assert payload["last_visit_date"] is None
    assert payload["matching_record_count"] == 0


# ---------------------------------------------------------------------------
# K.5 – latest date chosen from the later of the two sources
# ---------------------------------------------------------------------------
def test_k5_latest_date_chosen_across_both_sources():
    row = _roster_row()
    # TG file has the more recent date
    eligible_records = [_screening_record(date(2022, 1, 20))]
    eligible_history = [_tg_evidence(date(2024, 11, 5))]
    payload = ResultGenerationService._build_row_result_payload(
        row, eligible_records, eligible_history, _record_key_map()
    )
    assert payload["last_visit_date"] == date(2024, 11, 5), \
        "latest_relevant_date must come from the later evidence, regardless of source"

    # Screening DB has the more recent date
    payload2 = ResultGenerationService._build_row_result_payload(
        row,
        [_screening_record(date(2025, 3, 1))],
        [_tg_evidence(date(2024, 11, 5))],
        _record_key_map(),
    )
    assert payload2["last_visit_date"] == date(2025, 3, 1)


# ---------------------------------------------------------------------------
# K.6 – invalid (None) visit dates in TG evidence are excluded from latest-date
# ---------------------------------------------------------------------------
def test_k6_null_visit_dates_excluded_from_latest_date():
    row = _roster_row()
    # TG evidence with NULL visit date must not crash and must not pollute latest
    eligible_history = [
        _tg_evidence(None),               # blank date — must be skipped
        _tg_evidence(date(2024, 5, 20)),  # valid
    ]
    payload = ResultGenerationService._build_row_result_payload(
        row, [], eligible_history, _record_key_map()
    )
    assert payload["has_selected_service"] is True
    assert payload["last_visit_date"] == date(2024, 5, 20), \
        "None visit date must not corrupt latest-date calculation"


# ---------------------------------------------------------------------------
# K.7 – person with TG-file history is NOT classified as no_history_found
#        even when zero screening DB records exist (regression guard)
# ---------------------------------------------------------------------------
def test_k7_tg_history_prevents_no_history_classification():
    row = _roster_row()
    eligible_history = [_tg_evidence(date(2024, 2, 14))]
    payload = ResultGenerationService._build_row_result_payload(
        row, [], eligible_history, _record_key_map()
    )
    assert payload["result_status"] != "no_history_found", \
        "regression: person with TG-file history must not be labeled no_history_found"
    assert payload["result_status"] == "target_group_file_only"
    assert payload["has_selected_service"] is True
