"""
M.1 – M.4  source_history_for_result service-key expansion regression tests

Root cause documented: patient_query_service.source_history_for_result() was
filtering TargetGroupHistoryRow by raw selected_service_keys directly.
Pre-fix imports stored Thai slugs (e.g. "ตรวจมะเร็งปากมดลูก") instead of the
canonical key ("cervical_screen").  result_generation_service already handles
this via _expand_selected_service_keys(); source_history_for_result did not.

These tests verify:
  M.1  _expand_selected_service_keys expands "cervical_screen" → Thai slugs
  M.2  _expand_selected_service_keys expands "cervical_screen" → sub-keys
  M.3  source_history_for_result queries TG history with expanded eligible keys
  M.4  source_history_for_result returns pre-fix Thai-slug rows (regression guard)
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch
from uuid import uuid4

import pytest

from app.services.result_generation_service import ResultGenerationService


# ---------------------------------------------------------------------------
# M.1  _expand_selected_service_keys includes Thai slugs for cervical_screen
# ---------------------------------------------------------------------------

def test_m1_expand_includes_thai_slugs():
    """Expanding ["cervical_screen"] must include known Thai slug aliases."""
    _, record_to_selected = ResultGenerationService._expand_selected_service_keys(
        [], ["cervical_screen"]
    )
    eligible = set(record_to_selected.keys())
    thai_slugs_that_must_be_present = {
        "คัดกรองมะเร็งปากมดลูก",
        "ตรวจมะเร็งปากมดลูก",
        "ตรวจคัดกรองมะเร็งปากมดลูก",
        "มะเร็งปากมดลูก",
        "z124",
        "z12_4",
    }
    missing = thai_slugs_that_must_be_present - eligible
    assert not missing, (
        f"_expand_selected_service_keys must include Thai slug aliases; "
        f"missing: {missing}"
    )


# ---------------------------------------------------------------------------
# M.2  _expand_selected_service_keys includes cervical sub-keys
# ---------------------------------------------------------------------------

def test_m2_expand_includes_cervical_subkeys():
    """Expanding ["cervical_screen"] must include pap_smear, via, hpv sub-keys."""
    _, record_to_selected = ResultGenerationService._expand_selected_service_keys(
        [], ["cervical_screen"]
    )
    eligible = set(record_to_selected.keys())
    sub_keys = {"pap_smear", "via", "hpv", "other_method"}
    missing = sub_keys - eligible
    assert not missing, (
        f"_expand_selected_service_keys must include cervical sub-keys; "
        f"missing: {missing}"
    )


# ---------------------------------------------------------------------------
# M.3  source_history_for_result passes expanded eligible keys to TG query
# ---------------------------------------------------------------------------

def _make_mock_db(result_obj, screening_rows=None, tg_rows=None):
    """Return a MagicMock Session whose scalars().all() returns the given rows."""
    db = MagicMock()

    # db.get(TargetGroupResult, result_id) → result_obj
    db.get.return_value = result_obj

    # db.scalars(...).all() must handle two calls:
    # 1st call: DiseaseMapping query (for expansion)
    # 2nd call: DiseaseScreeningRecord query
    # 3rd call: TargetGroupHistoryRow query
    scalars_mock = MagicMock()
    scalars_mock.all.side_effect = [
        list(screening_rows or []),     # 1st call: DiseaseScreeningRecord (lines 144-153)
        [],                             # 2nd call: DiseaseMapping → no aliases (lines 179-180)
        list(tg_rows or []),            # 3rd call: TargetGroupHistoryRow (lines 197-199)
    ]
    db.scalars.return_value = scalars_mock
    return db


def _make_result(normalized_cid: str, group_job_id=None):
    return SimpleNamespace(
        id=uuid4(),
        group_job_id=group_job_id or uuid4(),
        normalized_cid=normalized_cid,
        full_name="นางสาว ทดสอบ",
    )


def test_m3_source_history_queries_with_expanded_keys():
    """
    source_history_for_result must call db.scalars() for TG history using
    expanded eligible keys (not just raw selected_service_keys).
    """
    from app.services.patient_query_service import PatientQueryService

    result = _make_result("1111111111111")
    db = _make_mock_db(result)

    # Patch _expand_selected_service_keys to spy on what keys are produced
    original_expand = ResultGenerationService._expand_selected_service_keys

    expanded_eligible_keys_used: list[str] = []

    def spy_expand(mapping_rows, selected_keys):
        selected_to_record, record_to_selected = original_expand(mapping_rows, selected_keys)
        expanded_eligible_keys_used.extend(sorted(record_to_selected.keys()))
        return selected_to_record, record_to_selected

    with patch.object(ResultGenerationService, "_expand_selected_service_keys", side_effect=spy_expand):
        PatientQueryService.source_history_for_result(
            db,
            result_id=result.id,
            selected_service_keys=["cervical_screen"],
        )

    assert "คัดกรองมะเร็งปากมดลูก" in expanded_eligible_keys_used, (
        "source_history_for_result must use expanded eligible keys including Thai slugs"
    )
    assert "z124" in expanded_eligible_keys_used


# ---------------------------------------------------------------------------
# M.4  source_history_for_result returns pre-fix Thai-slug rows  (regression)
# ---------------------------------------------------------------------------

def test_m4_pre_fix_thai_slug_rows_visible_in_modal():
    """
    A TargetGroupHistoryRow stored with normalized_service_key="ตรวจมะเร็งปากมดลูก"
    (pre-fix import) must appear in source_history_for_result when
    selected_service_keys=["cervical_screen"].

    Before the fix this test failed because the IN filter used the raw key list.
    After the fix, _expand_selected_service_keys adds Thai slugs so the row
    is included.
    """
    from datetime import date, datetime

    from app.services.patient_query_service import PatientQueryService

    group_id = uuid4()
    result = _make_result("1111111111111", group_job_id=group_id)

    # Pre-fix row — stored Thai slug, not "cervical_screen"
    tg_history_row = SimpleNamespace(
        source_file_name="กลุ่มเป้าหมาย.xlsx",
        source_sheet_name="ประวัติ",
        source_row_no=5,
        raw_service_type="ตรวจมะเร็งปากมดลูก",
        normalized_service_key="ตรวจมะเร็งปากมดลูก",  # ← pre-fix Thai slug
        normalized_visit_date=date(2023, 8, 15),
        raw_result="Negative",
        raw_hospital="รพ.ตัวอย่าง",
        raw_doctor=None,
        raw_note=None,
        validation_status="valid",
        warning_message=None,
    )

    db = _make_mock_db(result, tg_rows=[tg_history_row])

    response = PatientQueryService.source_history_for_result(
        db,
        result_id=result.id,
        selected_service_keys=["cervical_screen"],
    )

    assert len(response.target_group_history_events) == 1, (
        "REGRESSION: pre-fix Thai-slug TG history row must be visible in modal; "
        "source_history_for_result must expand service keys via _expand_selected_service_keys"
    )
    event = response.target_group_history_events[0]
    assert event["raw_service_type"] == "ตรวจมะเร็งปากมดลูก"
    assert response.history_source_summary == "target_group_file_only"
