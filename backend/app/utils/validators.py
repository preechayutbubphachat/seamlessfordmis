from collections.abc import Iterable

from app.utils.text_normalization import (
    DATE_VALID,
    IDENTIFIER_VALID,
    SERVICE_KNOWN,
)


def has_any_identifier(values: Iterable[str | None]) -> bool:
    return any(value not in (None, "") for value in values)


def is_valid_identifier_state(state: str | None) -> bool:
    return state == IDENTIFIER_VALID


def is_valid_date_state(state: str | None) -> bool:
    return state == DATE_VALID


def is_known_service_state(state: str | None) -> bool:
    return state == SERVICE_KNOWN
