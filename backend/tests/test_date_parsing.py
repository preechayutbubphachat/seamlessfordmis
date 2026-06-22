"""
N.1 – N.6  Thai Buddhist Era date parsing regression tests
===========================================================

Root cause documented: parse_date() (and parse_service_date()) passed Thai
Buddhist Era (พ.ศ.) year strings directly to pandas without converting the
year from BE to CE.  Since pandas Timestamp.max is CE 2262-04-11, any BE year
≥ 2263 (i.e. practically all modern Thai dates like year 2569) becomes NaT.

The fix adds _convert_be_to_ce() which replaces any 4-digit year ≥ 2500 in a
date string with (year − 543) before the string reaches pandas.

Tests
-----
N.1  dd/mm/YYYY BE string → correct CE date         "13/03/2569" → 2026-03-13
N.2  dd-mm-YYYY BE string → correct CE date         "13-03-2569" → 2026-03-13
N.3  YYYY-mm-dd BE string → correct CE date         "2569-03-13" → 2026-03-13
N.4  CE year unchanged                               "13/03/2026" → 2026-03-13
N.5  Adjacent BE years convert correctly             2569→2026, 2568→2025
N.6  parse_service_date propagates the BE fix        raw "13/03/2569" → normalized 2026-03-13
"""
from datetime import date

import pytest

from app.utils.dates import _convert_be_to_ce, parse_date
from app.utils.text_normalization import parse_service_date


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _date(y: int, m: int, d: int) -> date:
    return date(y, m, d)


# ---------------------------------------------------------------------------
# N.1  dd/mm/YYYY Buddhist Era string → CE date
# ---------------------------------------------------------------------------

def test_n1_slash_be_to_ce():
    """'13/03/2569' (Thai Buddhist year 2569 = CE 2026) must parse to 2026-03-13."""
    result = parse_date("13/03/2569")
    assert result == _date(2026, 3, 13), (
        f"Expected 2026-03-13 but got {result!r}. "
        "parse_date() must convert BE year 2569 → CE 2026 before calling pandas."
    )


# ---------------------------------------------------------------------------
# N.2  dd-mm-YYYY Buddhist Era string → CE date
# ---------------------------------------------------------------------------

def test_n2_dash_be_to_ce():
    """'13-03-2569' with dash separator must also convert correctly."""
    result = parse_date("13-03-2569")
    assert result == _date(2026, 3, 13), (
        f"Expected 2026-03-13 but got {result!r}."
    )


# ---------------------------------------------------------------------------
# N.3  YYYY-mm-dd Buddhist Era ISO-like string → CE date
# ---------------------------------------------------------------------------

def test_n3_iso_like_be_to_ce():
    """'2569-03-13' (ISO-like with BE year) must convert to 2026-03-13."""
    result = parse_date("2569-03-13")
    assert result == _date(2026, 3, 13), (
        f"Expected 2026-03-13 but got {result!r}."
    )


# ---------------------------------------------------------------------------
# N.4  CE year string must pass through unchanged
# ---------------------------------------------------------------------------

def test_n4_ce_year_unchanged():
    """'13/03/2026' (already CE year < 2500) must not be modified."""
    result = parse_date("13/03/2026")
    assert result == _date(2026, 3, 13), (
        f"Expected 2026-03-13 but got {result!r}. "
        "CE years (< 2500) must not be altered."
    )


# ---------------------------------------------------------------------------
# N.5  Adjacent Buddhist Era years convert correctly
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ("13/03/2569", _date(2026, 3, 13)),   # BE 2569 = CE 2026
    ("31/12/2568", _date(2025, 12, 31)),  # BE 2568 = CE 2025
    ("01/01/2567", _date(2024, 1, 1)),    # BE 2567 = CE 2024
    ("01/01/2500", _date(1957, 1, 1)),    # BE 2500 = CE 1957 (boundary)
    ("01/01/2023", _date(2023, 1, 1)),    # CE 2023 < 2500 → unchanged
])
def test_n5_adjacent_years(raw: str, expected: date):
    """Various BE and CE year strings must convert or pass through correctly."""
    result = parse_date(raw)
    assert result == expected, (
        f"parse_date({raw!r}): expected {expected} but got {result!r}"
    )


# ---------------------------------------------------------------------------
# N.6  parse_service_date propagates the BE fix
# ---------------------------------------------------------------------------

def test_n6_parse_service_date_be_year():
    """parse_service_date() must produce a valid normalized_value for a BE date string."""
    from app.utils.text_normalization import DATE_VALID

    result = parse_service_date("13/03/2569")
    assert result.normalized_value == _date(2026, 3, 13), (
        f"parse_service_date('13/03/2569').normalized_value: "
        f"expected 2026-03-13 but got {result.normalized_value!r}. "
        "parse_service_date delegates to parse_date() — the fix must propagate."
    )
    assert result.validation_state == DATE_VALID, (
        f"BE date string must produce validation_state=DATE_VALID ('{DATE_VALID}'); "
        f"got {result.validation_state!r}"
    )


# ---------------------------------------------------------------------------
# N.7  _convert_be_to_ce helper — low-level unit tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw,expected_str", [
    ("13/03/2569", "13/03/2026"),
    ("2569-03-13", "2026-03-13"),
    ("13/03/2026", "13/03/2026"),  # CE — no change
    ("13/03/2023", "13/03/2023"),  # below 2500 — no change
    ("01/01/2500", "01/01/1957"),  # boundary: exactly 2500
])
def test_n7_convert_be_to_ce_helper(raw: str, expected_str: str):
    """_convert_be_to_ce() string-level unit tests."""
    assert _convert_be_to_ce(raw) == expected_str, (
        f"_convert_be_to_ce({raw!r}): expected {expected_str!r}"
    )


# ---------------------------------------------------------------------------
# N.8  None and empty inputs still return None (regression guard)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bad_input", [None, "", "   ", "not-a-date", "00/00/0000"])
def test_n8_invalid_inputs_return_none(bad_input):
    """Non-date inputs must continue to return None, not raise."""
    result = parse_date(bad_input)
    assert result is None, (
        f"parse_date({bad_input!r}): expected None but got {result!r}"
    )
