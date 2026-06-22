from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


INDIVIDUAL_SHEET = "Individual"
DATA_START_ROW_INDEX = 8


@dataclass
class ParsedMainHistoryRow:
    source_filename: str
    source_sheet_name: str
    row_number: int
    values: dict[str, Any]


class ExcelMainHistoryImporter:
    COLUMN_MAP = {
        0: "report_row_no",
        1: "rep_no",
        2: "trans_id",
        3: "hn",
        4: "an",
        5: "raw_person_identifier",
        6: "full_name",
        7: "coverage_type",
        8: "hmain_op",
        9: "submitted_date",
        10: "raw_visit_date",
        11: "service_line_no",
        12: "raw_service_type",
        13: "quantity",
        14: "unit_price",
        15: "price_ceiling",
        16: "claimed_amount",
        17: "ps_code",
        18: "ps_percent",
        19: "compensated_amount",
        20: "not_compensated_amount",
        21: "extra_paid_amount",
        22: "reclaimed_amount",
        23: "claim_status",
        24: "remark",
        25: "stmid_remark",
        26: "hsend",
    }

    @classmethod
    def read_rows(cls, path: Path) -> list[ParsedMainHistoryRow]:
        if path.suffix.lower() == ".csv":
            return cls._read_csv_rows(path)
        workbook = pd.ExcelFile(path, engine=cls._resolve_excel_engine(path))
        sheet_name = INDIVIDUAL_SHEET if INDIVIDUAL_SHEET in workbook.sheet_names else workbook.sheet_names[0]
        frame = workbook.parse(sheet_name=sheet_name, header=None)
        rows: list[ParsedMainHistoryRow] = []

        for zero_index in range(DATA_START_ROW_INDEX, len(frame)):
            raw_row = frame.iloc[zero_index].tolist()
            mapped = cls._map_row(raw_row)
            if not cls._is_data_row(mapped):
                continue

            rows.append(
                ParsedMainHistoryRow(
                    source_filename=path.name,
                    source_sheet_name=sheet_name,
                    row_number=zero_index + 1,
                    values=mapped,
                )
            )

        return rows

    @staticmethod
    def _resolve_excel_engine(path: Path) -> str:
        return "xlrd" if path.suffix.lower() == ".xls" else "openpyxl"

    @classmethod
    def _read_csv_rows(cls, path: Path) -> list[ParsedMainHistoryRow]:
        frame = pd.read_csv(path, header=None)
        rows: list[ParsedMainHistoryRow] = []
        for zero_index in range(DATA_START_ROW_INDEX, len(frame)):
            raw_row = frame.iloc[zero_index].tolist()
            mapped = cls._map_row(raw_row)
            if not cls._is_data_row(mapped):
                continue
            rows.append(
                ParsedMainHistoryRow(
                    source_filename=path.name,
                    source_sheet_name="csv",
                    row_number=zero_index + 1,
                    values=mapped,
                )
            )
        return rows

    @classmethod
    def summarize_workbook(cls, path: Path) -> dict[str, Any]:
        rows = cls.read_rows(path)
        return {
            "filename": path.name,
            "sheet_name": rows[0].source_sheet_name if rows else INDIVIDUAL_SHEET,
            "row_count": len(rows),
        }

    @classmethod
    def _map_row(cls, row: Iterable[Any]) -> dict[str, Any]:
        values = list(row)
        mapped: dict[str, Any] = {}
        for index, key in cls.COLUMN_MAP.items():
            mapped[key] = values[index] if index < len(values) and pd.notna(values[index]) else None
        # Backward-compatible aliases while Phase 1 rolls out.
        mapped["pid"] = mapped.get("raw_person_identifier")
        mapped["visit_date"] = mapped.get("raw_visit_date")
        mapped["service_item_name"] = mapped.get("raw_service_type")
        mapped["VCTID,NAPNumber,PID"] = mapped.get("raw_person_identifier")
        return mapped

    @staticmethod
    def _is_data_row(row: dict[str, Any]) -> bool:
        return bool(row.get("rep_no") and row.get("full_name") and row.get("service_item_name"))
