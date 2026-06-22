from dataclasses import dataclass
from datetime import date
import re
import unicodedata

from app.utils.dates import parse_date


IDENTIFIER_VALID = "valid_identifier"
IDENTIFIER_INVALID = "invalid_identifier"
IDENTIFIER_MISSING = "missing_identifier"

DATE_VALID = "valid_date"
DATE_INVALID = "invalid_date"
DATE_MISSING = "missing_date"

SERVICE_KNOWN = "known_service"
SERVICE_UNKNOWN = "unknown_service"
SERVICE_MISSING = "missing_service"

SEX_MALE = "male"
SEX_FEMALE = "female"


@dataclass(frozen=True)
class IdentifierNormalizationResult:
    raw_value: str | None
    normalized_value: str | None
    validation_state: str
    looks_like_13_digit: bool
    removed_excel_decimal: bool = False


@dataclass(frozen=True)
class ServiceKeyNormalizationResult:
    raw_value: str | None
    normalized_value: str | None
    validation_state: str


@dataclass(frozen=True)
class DateNormalizationResult:
    raw_value: str | None
    normalized_value: date | None
    validation_state: str


@dataclass(frozen=True)
class IntegerNormalizationResult:
    raw_value: str | None
    normalized_value: int | None


@dataclass(frozen=True)
class SexNormalizationResult:
    raw_value: str | None
    normalized_value: str | None


def normalize_text(value: object | None) -> str | None:
    if value is None:
        return None
    normalized = unicodedata.normalize("NFKC", str(value)).strip()
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized or None


def _thai_id_check_digit_valid(digits: str) -> bool:
    """Validate Thai national ID check digit (algorithm: DOPA).

    sum   = digits[0]*13 + digits[1]*12 + ... + digits[11]*2
    check = (11 - sum % 11) % 10
    valid  iff check == int(digits[12])

    Only call with a string that already matches r'\\d{13}'.
    """
    total = sum(int(digits[i]) * (13 - i) for i in range(12))
    expected = (11 - (total % 11)) % 10
    return int(digits[12]) == expected


def normalize_identifier(value: object | None) -> IdentifierNormalizationResult:
    raw_text = normalize_text(value)
    if raw_text is None:
        return IdentifierNormalizationResult(
            raw_value=None,
            normalized_value=None,
            validation_state=IDENTIFIER_MISSING,
            looks_like_13_digit=False,
        )

    candidate = raw_text
    candidate = re.sub(r"[\s-]+", "", candidate)
    removed_excel_decimal = False
    if re.fullmatch(r"\d+\.0", candidate):
        candidate = candidate[:-2]
        removed_excel_decimal = True
    if not candidate:
        return IdentifierNormalizationResult(
            raw_value=raw_text,
            normalized_value=None,
            validation_state=IDENTIFIER_MISSING,
            looks_like_13_digit=False,
            removed_excel_decimal=removed_excel_decimal,
        )

    looks_like_13_digit = bool(re.fullmatch(r"\d{13}", candidate))
    if looks_like_13_digit:
        # Require valid Thai national ID check digit.
        # 13-digit strings with wrong checksums are staged as invalid_identifier
        # so operators can review them rather than silently getting wrong results.
        valid_checksum = _thai_id_check_digit_valid(candidate)
        validation_state = IDENTIFIER_VALID if valid_checksum else IDENTIFIER_INVALID
    else:
        validation_state = IDENTIFIER_INVALID
    return IdentifierNormalizationResult(
        raw_value=raw_text,
        normalized_value=candidate,
        validation_state=validation_state,
        looks_like_13_digit=looks_like_13_digit,
        removed_excel_decimal=removed_excel_decimal,
    )


def normalize_name(value: object | None) -> str | None:
    text = normalize_text(value)
    if text is None:
        return None
    lowered = text.casefold()
    return re.sub(r"\s+", " ", lowered).strip() or None


def normalize_service_key(value: object | None) -> ServiceKeyNormalizationResult:
    raw_text = normalize_text(value)
    if raw_text is None:
        return ServiceKeyNormalizationResult(
            raw_value=None,
            normalized_value=None,
            validation_state=SERVICE_MISSING,
        )

    lowered = raw_text.casefold()
    slug = lowered
    slug = re.sub(r"[\"'(),./:;]+", "", slug)
    slug = re.sub(r"[-\s]+", "_", slug).strip("_")
    return ServiceKeyNormalizationResult(
        raw_value=raw_text,
        normalized_value=slug or None,
        validation_state=SERVICE_KNOWN if slug else SERVICE_UNKNOWN,
    )


def parse_service_date(value: object | None) -> DateNormalizationResult:
    raw_text = normalize_text(value)
    if raw_text is None:
        return DateNormalizationResult(
            raw_value=None,
            normalized_value=None,
            validation_state=DATE_MISSING,
        )

    parsed = parse_date(value)
    if parsed is None:
        return DateNormalizationResult(
            raw_value=raw_text,
            normalized_value=None,
            validation_state=DATE_INVALID,
        )

    return DateNormalizationResult(
        raw_value=raw_text,
        normalized_value=parsed,
        validation_state=DATE_VALID,
    )


def normalize_age(value: object | None) -> IntegerNormalizationResult:
    raw_text = normalize_text(value)
    if raw_text is None:
        return IntegerNormalizationResult(raw_value=None, normalized_value=None)

    age_digits = re.sub(r"[^\d]", "", raw_text)
    if not age_digits:
        return IntegerNormalizationResult(raw_value=raw_text, normalized_value=None)

    try:
        parsed = int(age_digits)
    except ValueError:
        return IntegerNormalizationResult(raw_value=raw_text, normalized_value=None)

    if parsed < 0 or parsed > 130:
        return IntegerNormalizationResult(raw_value=raw_text, normalized_value=None)
    return IntegerNormalizationResult(raw_value=raw_text, normalized_value=parsed)


def normalize_sex(value: object | None) -> SexNormalizationResult:
    raw_text = normalize_text(value)
    if raw_text is None:
        return SexNormalizationResult(raw_value=None, normalized_value=None)

    lowered = raw_text.casefold()
    if lowered in {"ชาย", "ช", "male", "m"}:
        return SexNormalizationResult(raw_value=raw_text, normalized_value=SEX_MALE)
    if lowered in {"หญิง", "ญ", "female", "f"}:
        return SexNormalizationResult(raw_value=raw_text, normalized_value=SEX_FEMALE)
    return SexNormalizationResult(raw_value=raw_text, normalized_value=None)
