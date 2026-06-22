import re
from datetime import date, datetime

import pandas as pd

# ---------------------------------------------------------------------------
# Thai Buddhist Era (พ.ศ.) → Gregorian CE conversion
# ---------------------------------------------------------------------------
# Buddhist year 2500 = CE 1957.  Any 4-digit year ≥ 2500 appearing in a date
# string is almost certainly a Thai Buddhist year; subtract 543 to obtain the
# CE equivalent before handing the string to pandas.
#
# pandas Timestamp.max is CE 2262-04-11, so a raw BE year like 2569 (> 2262)
# is silently coerced to NaT without this pre-processing step.
#
# Pattern: 4-digit integer in the range 2500–9999 (word-boundary anchored so
# partial strings like "02569" are not matched).
_BE_YEAR_RE = re.compile(r"(?<!\d)(2[5-9]\d{2}|[3-9]\d{3})(?!\d)")


def _convert_be_to_ce(s: str) -> str:
    """Replace a Thai Buddhist Era year (≥ 2500) with the CE year (−543).

    Examples
    --------
    >>> _convert_be_to_ce("13/03/2569")
    '13/03/2026'
    >>> _convert_be_to_ce("2568-12-31")
    '2025-12-31'
    >>> _convert_be_to_ce("13/03/2026")   # CE year — unchanged
    '13/03/2026'
    """
    def _replace(m: re.Match) -> str:
        return str(int(m.group()) - 543)

    return _BE_YEAR_RE.sub(_replace, s)


def parse_date(value: object) -> date | None:
    if value is None:
        return None
    try:
        if pd.isna(value) or value == "":
            return None
    except Exception:
        if value == "":
            return None

    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None

        # Convert Thai Buddhist Era year to Gregorian CE before any parsing.
        # "13/03/2569" (BE) → "13/03/2026" (CE); CE years (< 2500) pass through
        # unchanged.
        stripped = _convert_be_to_ce(stripped)

        # Fast path for ISO-8601 date strings (YYYY-MM-DD) — avoids pandas overhead.
        if len(stripped) == 10 and stripped[4] == "-" and stripped[7] == "-":
            try:
                return date.fromisoformat(stripped)
            except ValueError:
                pass

        # General path: let pandas handle dd/mm/YYYY, dd-mm-YYYY, etc.
        try:
            parsed = pd.to_datetime(stripped, errors="coerce", dayfirst=True)
        except Exception:
            return None
        if pd.isna(parsed):
            return None
        return parsed.date()

    # Non-string path: datetime, date, pandas Timestamp, Excel serial float, etc.
    # These are already in CE — no BE conversion needed.
    try:
        parsed = pd.to_datetime(value, errors="coerce", dayfirst=True)
    except Exception:
        return None
    if pd.isna(parsed):
        return None
    return parsed.date()


def compute_visit_metrics(latest_visit_date: date | None) -> tuple[int | None, float | None]:
    if latest_visit_date is None:
        return None, None
    delta_days = (date.today() - latest_visit_date).days
    return delta_days, round(delta_days / 365.25, 2)


def utcnow() -> datetime:
    return datetime.utcnow()
