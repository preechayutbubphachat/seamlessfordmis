from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from uuid import uuid4

import pandas as pd

from app.schemas.result import (
    GroupResultRowResponse,
    GroupResultsResponse,
    ResultSummaryResponse,
    ServiceBreakdownResponse,
)
from app.services.export_service import ExportBundle, ExportService


@dataclass
class _FakeJob:
    id: object
    group_name: str


class _ScalarResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _FakeDb:
    def __init__(self, job, mapping_rows):
        self._job = job
        self._mapping_rows = mapping_rows

    def scalar(self, _query):
        return self._job

    def scalars(self, _query):
        return _ScalarResult(self._mapping_rows)


@dataclass
class _FakeMapping:
    normalized_key: str
    normalized_label: str


def _results_response(group_id):
    summary = ResultSummaryResponse(
        group_job_id=group_id,
        total_target_people=3,
        valid_identifier_people=2,
        invalid_identifier_people=1,
        people_with_selected_history=1,
        people_without_selected_history=1,
        coverage_percent=50.0,
        coverage_denominator="valid_identifier_people",
        coverage_denominator_people=2,
        selected_service_count=2,
        selected_service_keys=["svc_a", "svc_b"],
        generated_at=datetime(2026, 4, 20, 12, 0, 0),
    )
    rows = [
        GroupResultRowResponse(
            result_id=uuid4(),
            target_row_id=uuid4(),
            group_job_id=group_id,
            patient_id=None,
            normalized_cid="1234567890123",
            matched_identifier="1234567890123",
            full_name="สมหญิง ใจดี",
            age=42,
            sex="หญิง",
            match_status="matched",
            result_category="has_selected_history",
            result_status="has_selected_history",
            has_selected_service=True,
            matching_record_count=2,
            matched_service_keys=["svc_a"],
            last_visit_date=date(2026, 3, 1),
            days_since_last_visit=50,
            years_since_last_visit=0.14,
            warning_message=None,
        ),
        GroupResultRowResponse(
            result_id=uuid4(),
            target_row_id=uuid4(),
            group_job_id=group_id,
            patient_id=None,
            normalized_cid="9999999999999",
            matched_identifier="9999999999999",
            full_name="ใจดี สมชาย",
            age=51,
            sex="ชาย",
            match_status="not_found",
            result_category="no_selected_history",
            result_status="no_selected_history",
            has_selected_service=False,
            matching_record_count=0,
            matched_service_keys=[],
            last_visit_date=None,
            days_since_last_visit=None,
            years_since_last_visit=None,
            warning_message=None,
        ),
        GroupResultRowResponse(
            result_id=uuid4(),
            target_row_id=uuid4(),
            group_job_id=group_id,
            patient_id=None,
            normalized_cid=None,
            matched_identifier=None,
            full_name="ไม่ระบุ",
            age=None,
            sex=None,
            match_status="invalid",
            result_category="missing_identifier",
            result_status="missing_identifier",
            has_selected_service=False,
            matching_record_count=0,
            matched_service_keys=[],
            last_visit_date=None,
            days_since_last_visit=None,
            years_since_last_visit=None,
            warning_message="missing cid",
        ),
    ]
    return GroupResultsResponse(
        group_id=group_id,
        summary=summary,
        breakdown=[
            ServiceBreakdownResponse(selected_service_key="svc_a", distinct_people_count=1, matching_record_count=2),
            ServiceBreakdownResponse(selected_service_key="svc_b", distinct_people_count=0, matching_record_count=0),
        ],
        results=rows,
    )


def test_build_export_bundle_reuses_result_summary_and_labels(monkeypatch) -> None:
    group_id = uuid4()
    fake_results = _results_response(group_id)
    fake_db = _FakeDb(
        _FakeJob(group_id, "กลุ่มตรวจคัดกรอง 2569"),
        [_FakeMapping("svc_a", "คัดกรองมะเร็งปากมดลูก"), _FakeMapping("svc_b", "ตรวจคัดกรองตับอักเสบบี")],
    )

    monkeypatch.setattr("app.services.export_service.ResultGenerationService.get_results", lambda db, _group_id, **kwargs: fake_results)

    bundle = ExportService.build_export_bundle(fake_db, group_id, ["svc_b", "svc_a"])

    assert bundle.results.summary == fake_results.summary
    assert bundle.selected_service_labels == ["คัดกรองมะเร็งปากมดลูก", "ตรวจคัดกรองตับอักเสบบี"]
    assert len(bundle.results.results) == 3


def test_build_export_bundle_rejects_selection_mismatch(monkeypatch) -> None:
    group_id = uuid4()
    fake_results = _results_response(group_id)
    fake_db = _FakeDb(_FakeJob(group_id, "กลุ่ม A"), [])
    monkeypatch.setattr("app.services.export_service.ResultGenerationService.get_results", lambda db, _group_id, **kwargs: fake_results)

    try:
        ExportService.build_export_bundle(fake_db, group_id, ["svc_c"])
    except ValueError as exc:
        assert "ไม่ตรงกับผลลัพธ์ล่าสุด" in str(exc)
    else:
        raise AssertionError("expected selection mismatch error")


def test_write_excel_report_contains_summary_and_person_rows(tmp_path: Path) -> None:
    group_id = uuid4()
    bundle = ExportBundle(
        group_id=group_id,
        group_name="กลุ่ม B",
        results=_results_response(group_id),
        selected_service_labels=["คัดกรองมะเร็งปากมดลูก", "ตรวจคัดกรองตับอักเสบบี"],
    )
    output = tmp_path / "report.xlsx"

    ExportService._write_excel_report(bundle, output)

    summary_sheet = pd.read_excel(output, sheet_name="Summary")
    person_sheet = pd.read_excel(output, sheet_name="Person Results")

    assert output.exists()
    assert int(summary_sheet.loc[summary_sheet["รายการ"] == "จำนวนกลุ่มเป้าหมายทั้งหมด", "ค่า"].iloc[0]) == bundle.results.summary.total_target_people
    assert person_sheet.shape[0] == len(bundle.results.results)
    assert set(person_sheet["สถานะผลลัพธ์"]) == {"พบประวัติในรายการที่เลือก", "ไม่พบประวัติในรายการที่เลือก", "ไม่มีข้อมูลตัวระบุ"}


def test_write_csv_report_contains_same_person_row_count_and_context(tmp_path: Path) -> None:
    group_id = uuid4()
    bundle = ExportBundle(
        group_id=group_id,
        group_name="กลุ่ม C",
        results=_results_response(group_id),
        selected_service_labels=["คัดกรองมะเร็งปากมดลูก", "ตรวจคัดกรองตับอักเสบบี"],
    )
    output = tmp_path / "report.csv"

    ExportService._write_csv_report(bundle, output)

    frame = pd.read_csv(output, encoding="utf-8-sig")

    assert output.exists()
    assert frame.shape[0] == len(bundle.results.results)
    assert frame["รหัสกลุ่ม"].nunique() == 1
    assert frame["Coverage (%)"].iloc[0] == bundle.results.summary.coverage_percent
