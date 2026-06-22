from app.services.staging_validation_service import StagingValidationService


def test_main_history_row_requires_visit_date() -> None:
    normalized, issues = StagingValidationService.validate_main_history_row(
        2,
        {
            "VCTID,NAPNumber,PID": "1234567890123",
            "full_name": "สมหญิง ใจดี",
            "service_item_name": "คัดกรองเบาหวาน",
        },
    )

    assert normalized["normalized_person_identifier"] == "1234567890123"
    assert any(issue.field == "raw_visit_date" for issue in issues)
