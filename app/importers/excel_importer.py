from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


INDIVIDUAL_SHEET = "Individual"
HEADER_ROW_INDEX = 5
DATA_START_ROW_INDEX = 8
TARGET_GROUP_CERVICAL_HEADER_ROW_INDEX = 1
TARGET_GROUP_CERVICAL_DATA_START_ROW_INDEX = 3


@dataclass
class ParsedWorkbookRow:
    source_filename: str
    source_sheet_name: str
    row_number: int
    values: dict[str, Any]


@dataclass
class ParsedTargetGroupRow:
    source_filename: str
    source_sheet_name: str
    row_number: int
    values: dict[str, Any]


class ExcelImporter:
    COLUMN_MAP = {
        0: "report_row_no",
        1: "rep_no",
        2: "trans_id",
        3: "hn",
        4: "an",
        5: "pid",
        6: "full_name",
        7: "coverage_type",
        8: "hmain_op",
        9: "submitted_date",
        10: "visit_date",
        11: "service_line_no",
        12: "service_item_name",
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
    TARGET_GROUP_CERVICAL_COLUMN_MAP = {
        1: "external_person_id",
        2: "hn",
        3: "citizen_id",
        4: "full_name",
        5: "birth_date",
        6: "age_text",
        7: "sex",
        8: "nationality",
        9: "discharge_status",
        10: "type_area",
        11: "address",
        12: "screening_visit_date",
        13: "insurance_name",
        14: "cc",
        15: "icd10",
        16: "hospital_name",
        17: "doctor_name",
        18: "pap_smear_code",
        19: "pap_smear_result",
        20: "via_code",
        21: "via_result",
        22: "hpv_code",
        23: "hpv_result",
        24: "other_method_code",
        25: "other_method_result",
        26: "book_number",
        27: "reply_status",
        28: "reply_date",
        29: "payment_batch",
        30: "note",
        31: "workflow_status",
        32: "estimated_compensation",
        33: "hsub",
        34: "remark",
    }

    @classmethod
    def read_workbook_rows(cls, file_path: Path) -> list[ParsedWorkbookRow]:
        frame = pd.read_excel(file_path, sheet_name=INDIVIDUAL_SHEET, header=None, engine="openpyxl")
        rows: list[ParsedWorkbookRow] = []
        for zero_index in range(DATA_START_ROW_INDEX, len(frame)):
            row = frame.iloc[zero_index].tolist()
            mapped = cls._map_row(row)
            if not cls._is_data_row(mapped):
                continue
            rows.append(
                ParsedWorkbookRow(
                    source_filename=file_path.name,
                    source_sheet_name=INDIVIDUAL_SHEET,
                    row_number=zero_index + 1,
                    values=mapped,
                )
            )
        return rows

    @classmethod
    def _map_row(cls, row: list[Any]) -> dict[str, Any]:
        mapped: dict[str, Any] = {}
        for index, key in cls.COLUMN_MAP.items():
            mapped[key] = row[index] if index < len(row) and pd.notna(row[index]) else None
        return mapped

    @staticmethod
    def _is_data_row(row: dict[str, Any]) -> bool:
        return bool(row.get("rep_no") and row.get("full_name") and row.get("service_item_name"))

    @classmethod
    def summarize_workbook(cls, file_path: Path) -> dict[str, Any]:
        rows = cls.read_workbook_rows(file_path)
        return {
            "filename": file_path.name,
            "sheet_name": INDIVIDUAL_SHEET,
            "row_count": len(rows),
        }

    @classmethod
    def read_target_group_excel(cls, file_path: Path) -> list[ParsedTargetGroupRow]:
        engine = cls._resolve_excel_engine(file_path)
        if cls._looks_like_cervical_screening_target_group(file_path, engine):
            return cls._read_cervical_screening_target_group(file_path, engine)
        return cls._read_generic_target_group(file_path, engine)

    @staticmethod
    def _resolve_excel_engine(file_path: Path) -> str:
        return "xlrd" if file_path.suffix.lower() == ".xls" else "openpyxl"

    @classmethod
    def _looks_like_cervical_screening_target_group(cls, file_path: Path, engine: str) -> bool:
        preview = pd.read_excel(file_path, sheet_name=0, header=None, engine=engine, nrows=3)
        if len(preview) < 2:
            return False
        title = str(preview.iloc[0, 0]).strip() if pd.notna(preview.iloc[0, 0]) else ""
        header_row = [str(value).strip() for value in preview.iloc[TARGET_GROUP_CERVICAL_HEADER_ROW_INDEX].tolist()]
        return (
            "มะเร็งปากมดลูก" in title
            and "Person_ID" in header_row
            and "CID" in header_row
            and "ชื่อผู้ป่วย" in header_row
        )

    @classmethod
    def _read_cervical_screening_target_group(cls, file_path: Path, engine: str) -> list[ParsedTargetGroupRow]:
        frame = pd.read_excel(file_path, sheet_name=0, header=None, engine=engine)
        title = str(frame.iloc[0, 0]).strip() if pd.notna(frame.iloc[0, 0]) else ""
        sheet_name = "Sheet1"
        rows: list[ParsedTargetGroupRow] = []

        for zero_index in range(TARGET_GROUP_CERVICAL_DATA_START_ROW_INDEX, len(frame)):
            raw_row = frame.iloc[zero_index].tolist()
            mapped = cls._map_target_group_cervical_row(raw_row)
            if not cls._is_target_group_data_row(mapped):
                continue
            mapped["target_group_profile"] = "cervical_screening_registry_v1"
            mapped["source_title"] = title
            rows.append(
                ParsedTargetGroupRow(
                    source_filename=file_path.name,
                    source_sheet_name=sheet_name,
                    row_number=zero_index + 1,
                    values=mapped,
                )
            )

        return rows

    @classmethod
    def _map_target_group_cervical_row(cls, row: list[Any]) -> dict[str, Any]:
        mapped: dict[str, Any] = {
            "pid": None,
            "citizen_id": None,
            "hn": None,
            "full_name": None,
            "birth_date": None,
        }
        for index, key in cls.TARGET_GROUP_CERVICAL_COLUMN_MAP.items():
            mapped[key] = row[index] if index < len(row) and pd.notna(row[index]) else None

        mapped["citizen_id"] = mapped.get("citizen_id")
        mapped["hn"] = mapped.get("hn")
        mapped["full_name"] = mapped.get("full_name")
        mapped["birth_date"] = mapped.get("birth_date")
        return mapped

    @staticmethod
    def _is_target_group_data_row(row: dict[str, Any]) -> bool:
        return bool(row.get("citizen_id") or row.get("hn") or row.get("full_name"))

    @classmethod
    def _read_generic_target_group(cls, file_path: Path, engine: str) -> list[ParsedTargetGroupRow]:
        frame = pd.read_excel(file_path, engine=engine)
        safe_frame = frame.astype(object).where(pd.notnull(frame), None)
        rows: list[ParsedTargetGroupRow] = []
        for zero_index, row in enumerate(safe_frame.to_dict(orient="records"), start=2):
            rows.append(
                ParsedTargetGroupRow(
                    source_filename=file_path.name,
                    source_sheet_name="Sheet1",
                    row_number=zero_index,
                    values=row,
                )
            )
        return rows
