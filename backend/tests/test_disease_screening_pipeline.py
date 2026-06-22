from datetime import date
from uuid import uuid4

from app.models.staging_history_record import StagingHistoryRecord
from app.services.excel_main_import_service import ExcelMainImportService, StagingSummary
from app.services.merge_main_history_service import MergeMainHistoryService


def _build_staging_row(**overrides) -> StagingHistoryRecord:
    payload = {
        "import_job_id": uuid4(),
        "source_file_id": uuid4(),
        "source_file_name": "source.xlsx",
        "source_row_no": 9,
        "row_no": 9,
        "raw_person_identifier": "1234567890123",
        "raw_full_name": "สมหญิง ใจดี",
        "raw_service_type": "ตรวจคัดกรองเบาหวาน",
        "raw_visit_date": "17/04/2026",
        "raw_hcode": "12345",
        "raw_transaction_id": "TX-001",
        "raw_rep_no": "REP-01",
        "parse_status": "parsed",
        "validation_status": "valid",
        "identifier_validation_status": "valid_identifier",
        "date_validation_status": "valid_date",
        "service_validation_status": "known_service",
        "normalized_person_identifier": "1234567890123",
        "normalized_full_name": "สมหญิง ใจดี",
        "normalized_service_key": "ตรวจคัดกรองเบาหวาน",
        "normalized_visit_date": date(2026, 4, 17),
    }
    payload.update(overrides)
    return StagingHistoryRecord(**payload)


def test_classify_validation_status_marks_warning_without_row_errors() -> None:
    status = ExcelMainImportService._classify_validation_status(
        row_issues=[],
        warning_message="ยังไม่พบ disease mapping",
    )

    assert status == "warning"


def test_build_staging_history_record_preserves_provenance_and_raw_fields() -> None:
    record = ExcelMainImportService._build_staging_history_record(
        import_job_id=uuid4(),
        source_file_id=uuid4(),
        source_file_name="screening.xlsx",
        source_row_no=12,
        payload={"pid": "1234567890123", "birth_date": None},
        normalized={
            "raw_person_identifier": "1234567890123",
            "raw_full_name": "สมหญิง ใจดี",
            "raw_visit_date": "17/04/2026",
            "raw_service_type": "ตรวจเบาหวาน",
            "raw_hcode": "10999",
            "raw_transaction_id": "TXN-77",
            "raw_rep_no": "REP-77",
            "identifier_validation_status": "valid_identifier",
            "date_validation_status": "valid_date",
            "service_validation_status": "known_service",
            "normalized_person_identifier": "1234567890123",
            "pid": "1234567890123",
            "citizen_id": None,
            "hn": "HN001",
            "full_name": "สมหญิง ใจดี",
            "birth_date": None,
            "visit_date": date(2026, 4, 17),
            "normalized_service_key": "dm_screen",
            "diagnosis_code": None,
            "diagnosis_name": "ตรวจเบาหวาน",
            "raw_department": None,
            "raw_doctor_name": None,
        },
        validation_status="valid",
        row_issues=[],
        warning_message=None,
        disease_key="dm_screen",
        source_filename="screening.xlsx",
        source_sheet_name="Individual",
    )

    assert record.raw_hcode == "10999"
    assert record.raw_transaction_id == "TXN-77"
    assert record.raw_rep_no == "REP-77"
    assert record.source_row_no == 12
    assert record.raw_json["source_sheet_name"] == "Individual"


def test_invalid_identifier_row_stays_out_of_mergeable_set() -> None:
    row = _build_staging_row(
        raw_person_identifier="ABC-123",
        normalized_person_identifier="ABC123",
        identifier_validation_status="invalid_identifier",
        validation_status="invalid",
    )

    assert MergeMainHistoryService.is_mergeable_row(row) is False


def test_invalid_date_row_stays_out_of_mergeable_set() -> None:
    row = _build_staging_row(
        raw_visit_date="ไม่พบวันที่",
        normalized_visit_date=None,
        date_validation_status="invalid_date",
        validation_status="invalid",
    )

    assert MergeMainHistoryService.is_mergeable_row(row) is False


def test_valid_row_builds_clean_production_record() -> None:
    row = _build_staging_row()
    record = MergeMainHistoryService._build_disease_screening_record(row, row.import_job_id)

    assert record.raw_person_identifier == "1234567890123"
    assert record.normalized_person_identifier == "1234567890123"
    assert record.source_file_name == "source.xlsx"
    assert record.hcode == "12345"
    assert record.transaction_id == "TX-001"
    assert record.rep_no == "REP-01"


def test_duplicate_same_source_row_is_deduplicated_safely() -> None:
    import_job_id = uuid4()
    source_file_id = uuid4()
    row_a = _build_staging_row(import_job_id=import_job_id, source_file_id=source_file_id, source_row_no=15)
    row_b = _build_staging_row(import_job_id=import_job_id, source_file_id=source_file_id, source_row_no=15)

    deduped = MergeMainHistoryService._deduplicate_rows([row_a, row_b])

    assert len(deduped) == 1


def test_staging_summary_reports_skipped_rows_from_invalid_rows() -> None:
    summary = StagingSummary(total_rows=10, parsed_rows=10, valid_rows=6, invalid_rows=3, warning_rows=1)

    assert summary.skipped_rows == 3
