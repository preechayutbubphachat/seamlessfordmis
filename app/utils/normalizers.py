import re
from datetime import date, datetime
from numbers import Real
from typing import Any

import pandas as pd


def normalize_text(value: Any) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    if not text:
        return None
    return re.sub(r"\s+", " ", text)


def normalize_identifier(value: Any) -> str | None:
    if isinstance(value, Real) and not isinstance(value, bool):
        numeric_value = float(value)
        if numeric_value.is_integer():
            value = str(int(numeric_value))
    text = normalize_text(value)
    if not text:
        return None
    return re.sub(r"[^0-9A-Za-z]", "", text)


def normalize_name(value: Any) -> str | None:
    text = normalize_text(value)
    if not text:
        return None
    return re.sub(r"[^0-9A-Za-zก-๙]", "", text).lower()


def parse_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    parsed = pd.to_datetime(value, errors="coerce", dayfirst=True)
    if pd.isna(parsed):
        return None
    return parsed.date()
