from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pandas as pd

from app.importers.excel_target_group_importer import (
    ExcelTargetGroupImporter,
    ParsedTargetGroupRow,
    TARGET_GROUP_ROSTER,
    TARGET_GROUP_SCREENING_HISTORY,
)
from app.models.target_group_history_row import TargetGroupHistoryRow
from app.models.target_group_job import TargetGroupJob
from app.models.target_group_job_file import TargetGroupJobFile
from app.models.target_group_row import TargetGroupRow
from app.models.target_group_sheet import TargetGroupSheet
from app.services.field_mapping_service import FieldMappingService
from app.services.staging_validation_service import StagingValidationService
from app.services.target_group_import_service import TargetGroupImportService


class _FakeSession:
    def __init__(self) -> None:
        self.added: list[object] = []

    def add(self, obj: object) -> None:
        self.added.append(obj)

    def flush(self) -> None:
        return None


def _build_target_group_row(**overrides) -> TargetGroupRow:
    payload = {
        "group_job_id": uuid4(),
        "source_file_id": uuid4(),
        "source_file_name": "target.xlsx",
        "row_no": 2,
        "source_row_no": 2,
        "raw_cid": "1234567890121",
        "raw_full_name": "นางสาว ตัวอย่าง",
        "raw_age": "34",
        "raw_sex": "หญิง",
        "normalized_cid": "1234567890121",
        "normalized_full_name": "นางสาว ตัวอย่าง",
        "normalized_age": 34,
        "normalized_sex": "female",
        "parse_status": "parsed",
        "validation_status": "valid",
        "cid_validation_status": "valid_identifier",
        "duplicate_status": "unique_in_job",
        "match_status": "pending",
    }
    payload.update(overrides)
    return TargetGroupRow(**payload)


def test_target_group_row_accepts_cid_only() -> None:
    normalized, issues = StagingValidationService.validate_target_group_row(
        2,
        {
            "CID": "1234567890121",
            "ชื่อผู้ป่วย": "นางสาวตัวอย่าง",
        },
    )

    assert normalized["normalized_cid"] == "1234567890121"
    assert issues == []


def test_field_mapping_normalizes_cid_age_and_sex() -> None:
    normalized = FieldMappingService.map_target_group_row(
        {
            "CID": "123-456-7890121.0",
            "ชื่อผู้ป่วย": "นางสาว ตัวอย่าง",
            "อายุ": "34 ปี",
            "เพศ": "หญิง",
        }
    )

    assert normalized["raw_cid"] == "123-456-7890121.0"
    assert normalized["normalized_cid"] == "1234567890121"
    assert normalized["normalized_age"] == 34
    assert normalized["normalized_sex"] == "female"


def test_stage_rows_preserves_file_provenance_and_target_group_history_context() -> None:
    db = _FakeSession()
    job = TargetGroupJob(
        group_name="กลุ่มตัวอย่าง",
        source_file_name="target.xlsx",
        source_file_type="excel",
        source_file_hash="x" * 64,
        source_set_hash="y" * 64,
        source_file_count=1,
        parse_status="processing",
        match_status="pending",
    )
    job.id = uuid4()
    job_file = TargetGroupJobFile(
        group_job_id=job.id,
        file_name="target.xlsx",
        file_path="C:/tmp/target.xlsx",
        file_type="excel",
        sha256="a" * 64,
        parse_status="processing",
    )
    job_file.id = uuid4()

    rows = [
        ParsedTargetGroupRow(
            source_filename="target.xlsx",
            source_sheet_name="Sheet1",
            source_sheet_index=0,
            row_number=7,
            values={
                "CID": "1234567890121",
                "ชื่อผู้ป่วย": "นางสาว ตัวอย่าง",
                "อายุ": "34",
                "เพศ": "หญิง",
                "pap_smear_result": "Negative",
                "screening_visit_date": "2025-01-01",
                "note": "ติดตามต่อเนื่อง",
            },
        )
    ]
    preview_rows = []

    source_sheet = TargetGroupSheet(
        group_job_id=job.id,
        source_file_id=job_file.id,
        sheet_name="Sheet1",
        sheet_index=0,
        sheet_type="mixed_sheet",
        row_count=1,
        column_names_json=["CID", "ชื่อผู้ป่วย", "pap_smear_result"],
    )
    source_sheet.id = uuid4()

    summary, issues = TargetGroupImportService._stage_rows(
        db,
        job,
        job_file,
        rows,
        {(0, "Sheet1"): source_sheet},
        preview_rows,
    )

    assert issues == []
    assert summary.total_rows == 1
    staged = next(obj for obj in db.added if isinstance(obj, TargetGroupRow))
    assert staged.source_file_id == job_file.id
    assert staged.source_file_name == "target.xlsx"
    assert staged.source_row_no == 7
    assert staged.raw_cid == "1234567890121"
    assert staged.raw_target_history_labels is not None
    assert staged.normalized_target_history_service_keys == ["cervical_screen", "pap_smear"]
    assert staged.raw_json["source_sheet_name"] == "Sheet1"
    assert preview_rows[0].row_no == 7
    staged_history = next(obj for obj in db.added if isinstance(obj, TargetGroupHistoryRow))
    assert staged_history.normalized_service_key == "cervical_screen"
    assert staged_history.source_row_no == 7
    assert staged_history.source_sheet_id == source_sheet.id


def test_invalid_cid_rows_remain_visible_in_summary() -> None:
    rows = [
        _build_target_group_row(
            row_no=2,
            raw_cid="ABC-123",
            normalized_cid="ABC123",
            cid_validation_status="invalid_identifier",
            validation_status="invalid",
        ),
        _build_target_group_row(
            row_no=3,
            raw_cid=None,
            normalized_cid=None,
            cid_validation_status="missing_identifier",
            validation_status="invalid",
        ),
    ]

    summary = TargetGroupImportService._summarize_rows(rows, total_uploaded_files=1)

    assert summary.total_rows == 2
    assert summary.invalid_cid_rows == 1
    assert summary.missing_cid_rows == 1
    assert summary.valid_cid_rows == 0


def test_duplicate_cid_detection_is_surfaced_in_summary() -> None:
    rows = [
        _build_target_group_row(row_no=2, duplicate_status="duplicate_in_job", validation_status="warning"),
        _build_target_group_row(row_no=3, duplicate_status="duplicate_in_job", validation_status="warning"),
        _build_target_group_row(row_no=4, normalized_cid="9999999999999"),
    ]

    summary = TargetGroupImportService._summarize_rows(rows, total_uploaded_files=2)

    assert summary.total_uploaded_files == 2
    assert summary.duplicate_cid_rows == 2
    assert summary.warning_rows == 2
    assert summary.valid_cid_rows == 1


def test_parse_error_summary_lists_key_problems() -> None:
    summary = TargetGroupImportService._summarize_rows(
        [
            _build_target_group_row(
                row_no=2,
                cid_validation_status="invalid_identifier",
                validation_status="invalid",
            ),
            _build_target_group_row(
                row_no=3,
                cid_validation_status="missing_identifier",
                normalized_cid=None,
                parse_status="parse_failed",
                validation_status="invalid",
            ),
            _build_target_group_row(
                row_no=4,
                duplicate_status="duplicate_in_job",
                validation_status="warning",
            ),
        ],
        total_uploaded_files=1,
    )

    text = TargetGroupImportService._build_parse_error_summary(summary)

    assert text is not None
    assert "CID" in text


def test_validate_upload_batch_rejects_duplicate_files_in_same_request() -> None:
    fingerprints = [
        SimpleNamespace(filename="group-a.xlsx", sha256="same-hash"),
        SimpleNamespace(filename="group-b.xlsx", sha256="same-hash"),
    ]

    try:
        TargetGroupImportService._validate_upload_batch(fingerprints)
    except ValueError as exc:
        assert "ไฟล์ซ้ำ" in str(exc)
    else:
        raise AssertionError("expected duplicate upload validation to fail")


def test_importer_reads_multiple_sheets_and_classifies_history_sheet(tmp_path: Path) -> None:
    workbook_path = tmp_path / "multi-sheet-target-group.xlsx"
    roster_frame = pd.DataFrame(
        [
            {"CID": "1234567890121", "ชื่อผู้ป่วย": "นางสาว ตัวอย่าง", "อายุ": "34", "เพศ": "หญิง"},
        ]
    )
    history_frame = pd.DataFrame(
        [
            {"CID": "1234567890121", "ชื่อผู้ป่วย": "นางสาว ตัวอย่าง", "วันที่ตรวจ": "2025-01-01", "HPV": "Negative", "ผลการตรวจ": "Negative"},
        ]
    )
    with pd.ExcelWriter(workbook_path, engine="openpyxl") as writer:
        roster_frame.to_excel(writer, sheet_name="รายชื่อกลุ่มเป้าหมาย", index=False)
        history_frame.to_excel(writer, sheet_name="ประวัติการตรวจ", index=False)

    workbook = ExcelTargetGroupImporter.read_workbook(workbook_path)
    rows = workbook.rows

    assert any(row.sheet_type == TARGET_GROUP_ROSTER for row in rows)
    assert any(row.sheet_type == TARGET_GROUP_SCREENING_HISTORY for row in rows)
    assert len(workbook.sheets) == 2
    assert any(sheet.sheet_type == TARGET_GROUP_ROSTER for sheet in workbook.sheets)
    assert any(sheet.sheet_type == TARGET_GROUP_SCREENING_HISTORY for sheet in workbook.sheets)


def test_stage_rows_persists_target_group_history_rows_from_history_sheet() -> None:
    db = _FakeSession()
    job = TargetGroupJob(
        group_name="กลุ่มตัวอย่าง",
        source_file_name="target.xlsx",
        source_file_type="excel",
        source_file_hash="x" * 64,
        source_set_hash="y" * 64,
        source_file_count=1,
        parse_status="processing",
        match_status="pending",
    )
    job.id = uuid4()
    job_file = TargetGroupJobFile(
        group_job_id=job.id,
        file_name="target.xlsx",
        file_path="C:/tmp/target.xlsx",
        file_type="excel",
        sha256="a" * 64,
        parse_status="processing",
    )
    job_file.id = uuid4()

    rows = [
        ParsedTargetGroupRow(
            source_filename="target.xlsx",
            source_sheet_name="ประวัติการตรวจ",
            source_sheet_index=1,
            row_number=10,
            sheet_type=TARGET_GROUP_SCREENING_HISTORY,
            values={
                "CID": "1234567890121",
                "ชื่อผู้ป่วย": "นางสาว ตัวอย่าง",
                "วันที่ตรวจ": "2025-01-01",
                "pap_smear_result": "Negative",
                "hospital_name": "รพ.ตัวอย่าง",
            },
        )
    ]

    source_sheet = TargetGroupSheet(
        group_job_id=job.id,
        source_file_id=job_file.id,
        sheet_name="ประวัติการตรวจ",
        sheet_index=1,
        sheet_type=TARGET_GROUP_SCREENING_HISTORY,
        row_count=1,
        column_names_json=["CID", "ชื่อผู้ป่วย", "วันที่ตรวจ", "pap_smear_result", "hospital_name"],
    )
    source_sheet.id = uuid4()

    summary, issues = TargetGroupImportService._stage_rows(
        db,
        job,
        job_file,
        rows,
        {(1, "ประวัติการตรวจ"): source_sheet},
        preview_rows=[],
    )

    assert issues == []
    assert summary.total_rows == 0
    staged_history = next(obj for obj in db.added if isinstance(obj, TargetGroupHistoryRow))
    assert staged_history.source_sheet_name == "ประวัติการตรวจ"
    assert staged_history.source_sheet_id == source_sheet.id
    assert staged_history.normalized_cid == "1234567890121"
    assert staged_history.normalized_service_key == "cervical_screen"
    assert staged_history.normalized_visit_date is not None


# ---------------------------------------------------------------------------
# H.1 – H.7  Multi-sheet ingestion tests (Phase B)
# ---------------------------------------------------------------------------

import io
from unittest.mock import patch

from app.importers.excel_target_group_importer import (
    HISTORY_SHEET,
    MIXED_SHEET,
    ROSTER_SHEET,
    UNKNOWN_SHEET,
    ParsedTargetGroupSheet,
    ParsedTargetGroupWorkbook,
)


def _make_job_and_file():
    job = TargetGroupJob(
        group_name="test-group",
        source_file_name="test.xlsx",
        source_file_type="excel",
        source_file_hash="h" * 64,
        source_set_hash="s" * 64,
        source_file_count=1,
        parse_status="processing",
        match_status="pending",
    )
    job.id = uuid4()
    job_file = TargetGroupJobFile(
        group_job_id=job.id,
        file_name="test.xlsx",
        file_path="C:/tmp/test.xlsx",
        file_type="excel",
        sha256="a" * 64,
        parse_status="processing",
    )
    job_file.id = uuid4()
    return job, job_file


def _make_sheet(job, job_file, name, index, sheet_type, columns=None):
    sheet = TargetGroupSheet(
        group_job_id=job.id,
        source_file_id=job_file.id,
        sheet_name=name,
        sheet_index=index,
        sheet_type=sheet_type,
        row_count=1,
        column_names_json=columns or ["CID", "ชื่อผู้ป่วย"],
    )
    sheet.id = uuid4()
    return sheet


def _roster_row(job_file, sheet_name="รายชื่อ", sheet_index=0, row_number=2):
    return ParsedTargetGroupRow(
        source_filename=job_file.file_name,
        source_sheet_name=sheet_name,
        source_sheet_index=sheet_index,
        row_number=row_number,
        sheet_type=ROSTER_SHEET,
        values={
            "CID": "1111111111119",
            "ชื่อผู้ป่วย": "นางสาว ก",
            "อายุ": "45",
            "เพศ": "หญิง",
        },
    )


def _history_row(job_file, sheet_name="ประวัติ", sheet_index=1, row_number=2):
    return ParsedTargetGroupRow(
        source_filename=job_file.file_name,
        source_sheet_name=sheet_name,
        source_sheet_index=sheet_index,
        row_number=row_number,
        sheet_type=HISTORY_SHEET,
        values={
            "CID": "2222222222222",
            "ชื่อผู้ป่วย": "นางสาว ข",
            "วันที่ตรวจ": "2024-06-01",
            "pap_smear_result": "Negative",
        },
    )


# H.1 – Single roster sheet produces TargetGroupRow entries only, no history rows
def test_h1_single_roster_sheet_stages_only_roster_rows():
    db = _FakeSession()
    job, job_file = _make_job_and_file()
    sheet = _make_sheet(job, job_file, "รายชื่อ", 0, ROSTER_SHEET)
    rows = [_roster_row(job_file, "รายชื่อ", 0, 2)]
    sheet_lookup = {(0, "รายชื่อ"): sheet}

    summary, issues = TargetGroupImportService._stage_rows(
        db, job, job_file, rows, sheet_lookup, preview_rows=[]
    )

    assert issues == []
    tg_rows = [o for o in db.added if isinstance(o, TargetGroupRow)]
    history_rows = [o for o in db.added if isinstance(o, TargetGroupHistoryRow)]
    assert len(tg_rows) == 1, "expected one TargetGroupRow for a roster row"
    assert len(history_rows) == 0, "roster-only sheet must not produce TargetGroupHistoryRow"
    assert tg_rows[0].normalized_cid == "1111111111119"


# H.2 – Roster sheet + history sheet: history rows are staged with correct provenance
def test_h2_history_sheet_rows_are_staged_with_correct_provenance():
    db = _FakeSession()
    job, job_file = _make_job_and_file()
    roster_sheet = _make_sheet(job, job_file, "รายชื่อ", 0, ROSTER_SHEET)
    history_sheet = _make_sheet(
        job, job_file, "ประวัติ", 1, HISTORY_SHEET,
        columns=["CID", "ชื่อผู้ป่วย", "วันที่ตรวจ", "pap_smear_result"],
    )
    rows = [
        _roster_row(job_file, "รายชื่อ", 0, 2),
        _history_row(job_file, "ประวัติ", 1, 3),
    ]
    sheet_lookup = {(0, "รายชื่อ"): roster_sheet, (1, "ประวัติ"): history_sheet}

    summary, issues = TargetGroupImportService._stage_rows(
        db, job, job_file, rows, sheet_lookup, preview_rows=[]
    )

    tg_rows = [o for o in db.added if isinstance(o, TargetGroupRow)]
    history_rows = [o for o in db.added if isinstance(o, TargetGroupHistoryRow)]
    assert len(tg_rows) == 1
    assert len(history_rows) == 1
    hr = history_rows[0]
    assert hr.source_sheet_name == "ประวัติ"
    assert hr.source_sheet_id == history_sheet.id
    assert hr.source_row_no == 3
    assert hr.normalized_cid == "2222222222222"


# H.3 – Mixed sheet produces both a roster row AND a history row
def test_h3_mixed_sheet_stages_roster_and_history_rows():
    db = _FakeSession()
    job, job_file = _make_job_and_file()
    mixed_sheet = _make_sheet(
        job, job_file, "รายการ", 0, MIXED_SHEET,
        columns=["CID", "ชื่อผู้ป่วย", "วันที่ตรวจ", "pap_smear_result", "screening_visit_date"],
    )
    mixed_row = ParsedTargetGroupRow(
        source_filename=job_file.file_name,
        source_sheet_name="รายการ",
        source_sheet_index=0,
        row_number=2,
        sheet_type=MIXED_SHEET,
        values={
            "CID": "3333333333333",
            "ชื่อผู้ป่วย": "นาง ค",
            "อายุ": "50",
            "เพศ": "หญิง",
            "วันที่ตรวจ": "2024-09-15",
            "pap_smear_result": "Negative",
            "screening_visit_date": "2024-09-15",
        },
    )
    sheet_lookup = {(0, "รายการ"): mixed_sheet}

    summary, issues = TargetGroupImportService._stage_rows(
        db, job, job_file, [mixed_row], sheet_lookup, preview_rows=[]
    )

    tg_rows = [o for o in db.added if isinstance(o, TargetGroupRow)]
    history_rows = [o for o in db.added if isinstance(o, TargetGroupHistoryRow)]
    assert len(tg_rows) == 1, "mixed sheet must produce a TargetGroupRow"
    assert len(history_rows) == 1, "mixed sheet must also produce a TargetGroupHistoryRow"
    assert history_rows[0].source_sheet_id == mixed_sheet.id


# H.4 – Unknown sheet with identity columns is staged as unclassified, not dropped
def test_h4_unknown_sheet_rows_with_identity_are_staged_as_unclassified():
    db = _FakeSession()
    job, job_file = _make_job_and_file()
    unknown_sheet = _make_sheet(job, job_file, "แผ่นข้อมูล", 0, UNKNOWN_SHEET)
    unknown_row = ParsedTargetGroupRow(
        source_filename=job_file.file_name,
        source_sheet_name="แผ่นข้อมูล",
        source_sheet_index=0,
        row_number=5,
        sheet_type=UNKNOWN_SHEET,
        sheet_warning="sheet 'แผ่นข้อมูล' ยังจัดประเภทไม่ได้อย่างปลอดภัย",
        values={
            "CID": "4444444444444",
            "ชื่อผู้ป่วย": "นาย ง",
            "some_column": "some_value",
        },
    )
    sheet_lookup = {(0, "แผ่นข้อมูล"): unknown_sheet}

    summary, issues = TargetGroupImportService._stage_rows(
        db, job, job_file, [unknown_row], sheet_lookup, preview_rows=[]
    )

    # No TargetGroupRow — unknown sheet rows don't become roster entries
    tg_rows = [o for o in db.added if isinstance(o, TargetGroupRow)]
    assert len(tg_rows) == 0

    # One TargetGroupHistoryRow with unclassified status
    history_rows = [o for o in db.added if isinstance(o, TargetGroupHistoryRow)]
    assert len(history_rows) == 1, "unknown-sheet row with identity column must be staged"
    hr = history_rows[0]
    assert hr.validation_status == "unclassified"
    assert hr.normalized_cid == "4444444444444"
    assert "unclassified_sheet" in (hr.warning_message or "")


# H.5 – Provenance fields (file/sheet/row) are present on every staged object
def test_h5_provenance_fields_on_every_staged_object():
    db = _FakeSession()
    job, job_file = _make_job_and_file()
    sheet = _make_sheet(job, job_file, "รายชื่อ", 0, ROSTER_SHEET)
    rows = [_roster_row(job_file, "รายชื่อ", 0, 7)]
    sheet_lookup = {(0, "รายชื่อ"): sheet}

    TargetGroupImportService._stage_rows(
        db, job, job_file, rows, sheet_lookup, preview_rows=[]
    )

    for obj in db.added:
        if isinstance(obj, TargetGroupRow):
            assert obj.source_file_name == job_file.file_name, "TargetGroupRow missing source_file_name"
            assert obj.source_row_no == 7, "TargetGroupRow missing source_row_no"
        elif isinstance(obj, TargetGroupHistoryRow):
            assert obj.source_file_name == job_file.file_name
            assert obj.source_row_no == 7


# H.6 – _persist_sheet_metadata creates one TargetGroupSheet per parsed sheet
def test_h6_persist_sheet_metadata_creates_one_sheet_per_parsed_sheet():
    db = _FakeSession()
    job, job_file = _make_job_and_file()

    parsed_sheets = [
        ParsedTargetGroupSheet(
            source_filename="test.xlsx",
            sheet_name="รายชื่อ",
            sheet_index=0,
            sheet_type=ROSTER_SHEET,
            row_count=5,
            column_names=["CID", "ชื่อผู้ป่วย"],
            classification_confidence=0.85,
        ),
        ParsedTargetGroupSheet(
            source_filename="test.xlsx",
            sheet_name="ประวัติ",
            sheet_index=1,
            sheet_type=HISTORY_SHEET,
            row_count=3,
            column_names=["CID", "วันที่ตรวจ"],
            classification_confidence=0.9,
        ),
    ]

    lookup = TargetGroupImportService._persist_sheet_metadata(db, job.id, job_file, parsed_sheets)

    sheet_objs = [o for o in db.added if isinstance(o, TargetGroupSheet)]
    assert len(sheet_objs) == 2
    assert (0, "รายชื่อ") in lookup
    assert (1, "ประวัติ") in lookup
    assert lookup[(0, "รายชื่อ")].sheet_type == ROSTER_SHEET
    assert lookup[(1, "ประวัติ")].sheet_type == HISTORY_SHEET


# H.7 – TargetGroupHistoryRows from a non-first sheet are linked via correct source_sheet_id
def test_h7_history_rows_from_second_sheet_linked_to_correct_source_sheet():
    db = _FakeSession()
    job, job_file = _make_job_and_file()

    sheet0 = _make_sheet(job, job_file, "รายชื่อ", 0, ROSTER_SHEET)
    sheet1 = _make_sheet(
        job, job_file, "ประวัติ", 1, HISTORY_SHEET,
        columns=["CID", "ชื่อผู้ป่วย", "วันที่ตรวจ", "pap_smear_result"],
    )
    sheet2 = _make_sheet(
        job, job_file, "ประวัติ2", 2, HISTORY_SHEET,
        columns=["CID", "ชื่อผู้ป่วย", "วันที่ตรวจ", "pap_smear_result"],
    )

    rows = [
        _roster_row(job_file, "รายชื่อ", 0, 2),
        _history_row(job_file, "ประวัติ", 1, 3),
        ParsedTargetGroupRow(
            source_filename=job_file.file_name,
            source_sheet_name="ประวัติ2",
            source_sheet_index=2,
            row_number=4,
            sheet_type=HISTORY_SHEET,
            values={
                "CID": "3333333333333",
                "ชื่อผู้ป่วย": "นาย ค",
                "วันที่ตรวจ": "2023-03-10",
                "pap_smear_result": "Negative",
            },
        ),
    ]
    sheet_lookup = {(0, "รายชื่อ"): sheet0, (1, "ประวัติ"): sheet1, (2, "ประวัติ2"): sheet2}

    TargetGroupImportService._stage_rows(
        db, job, job_file, rows, sheet_lookup, preview_rows=[]
    )

    history_rows = [o for o in db.added if isinstance(o, TargetGroupHistoryRow)]
    assert len(history_rows) == 2

    by_sheet = {hr.source_sheet_name: hr for hr in history_rows}
    assert by_sheet["ประวัติ"].source_sheet_id == sheet1.id
    assert by_sheet["ประวัติ2"].source_sheet_id == sheet2.id
    assert by_sheet["ประวัติ2"].source_row_no == 4
