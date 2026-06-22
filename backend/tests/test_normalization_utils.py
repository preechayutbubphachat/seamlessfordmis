from datetime import date

from app.utils.text_normalization import (
    IDENTIFIER_INVALID,
    IDENTIFIER_VALID,
    SERVICE_KNOWN,
    SERVICE_MISSING,
    DATE_VALID,
    normalize_identifier,
    normalize_service_key,
    parse_service_date,
)


def test_normalize_identifier_removes_safe_separators_and_excel_decimal() -> None:
    # 1234567890121 passes the Thai DOPA mod-11 check digit (synthetic, not a real person)
    result = normalize_identifier(" 123-456-7890121.0 ")

    assert result.normalized_value == "1234567890121"
    assert result.validation_state == IDENTIFIER_VALID
    assert result.looks_like_13_digit is True
    assert result.removed_excel_decimal is True


def test_normalize_identifier_rejects_13_digit_with_bad_check_digit() -> None:
    # Looks like a CID (13 digits) but fails the DOPA mod-11 checksum —
    # must be classified invalid_identifier, never valid, never silently no-history.
    result = normalize_identifier("1234567890123")

    assert result.looks_like_13_digit is True
    assert result.validation_state == IDENTIFIER_INVALID
    assert result.normalized_value == "1234567890123"

    result_zeros = normalize_identifier("1234567890000")

    assert result_zeros.looks_like_13_digit is True
    assert result_zeros.validation_state == IDENTIFIER_INVALID


def test_normalize_identifier_marks_non_13_digit_as_invalid() -> None:
    result = normalize_identifier("ABC-123")

    assert result.validation_state == IDENTIFIER_INVALID
    assert result.normalized_value == "ABC123"


def test_normalize_service_key_builds_comparable_key() -> None:
    result = normalize_service_key("ตรวจคัดกรอง เบาหวาน")

    assert result.validation_state == SERVICE_KNOWN
    assert result.normalized_value == "ตรวจคัดกรอง_เบาหวาน"


def test_parse_service_date_returns_valid_date() -> None:
    result = parse_service_date("17/04/2026")

    assert result.validation_state == DATE_VALID
    assert result.normalized_value == date(2026, 4, 17)


def test_missing_service_is_classified_explicitly() -> None:
    result = normalize_service_key(None)

    assert result.validation_state == SERVICE_MISSING
    assert result.normalized_value is None
