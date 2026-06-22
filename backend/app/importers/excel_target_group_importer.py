from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd


TARGET_GROUP_CERVICAL_HEADER_ROW_INDEX = 1
TARGET_GROUP_CERVICAL_DATA_START_ROW_INDEX = 3

ROSTER_SHEET = "roster_sheet"
HISTORY_SHEET = "history_sheet"
MIXED_SHEET = "mixed_sheet"
UNKNOWN_SHEET = "unknown_sheet"

# Backward-compatible aliases used by older services/tests.
TARGET_GROUP_ROSTER = ROSTER_SHEET
TARGET_GROUP_SCREENING_HISTORY = HISTORY_SHEET
TARGET_GROUP_OTHER_CONTEXT = MIXED_SHEET
UNKNOWN_SHEET_TYPE = UNKNOWN_SHEET

PERSON_IDENTITY_COLUMNS = {
    "cid",
    "citizen_id",
    "raw_cid",
    "ชื่อผู้ป่วย",
    "ชื่อ-สกุล",
    "full_name",
    "name",
}

ROSTER_CONTEXT_COLUMNS = {
    "hn",
    "age",
    "age_text",
    "อายุ",
    "sex",
    "เพศ",
    "birth_date",
    "วันเกิด",
    "nationality",
    "สัญชาติ",
    "address",
    "ที่อยู่",
}

HISTORY_HINT_COLUMNS = {
    # Clinical visit / event columns — these are the true discriminating hints.
    # Demographic fields (birth_date, nationality, address) are intentionally
    # excluded: they appear in roster sheets too and would cause pure-roster
    # sheets to be misclassified as MIXED_SHEET.
    "วันที่ตรวจ",
    "visit_date",
    "screening_visit_date",
    "วันที่รับบริการ",
    "last_visit_date",
    "icd10",
    "hpv",
    "hpv_result",
    "ผลการตรวจ",
    "pap_smear_result",
    "via_result",
    "hospital_name",
    "สถานพยาบาล",
    "doctor_name",
    "ชื่อแพทย์",
    "หมายเหตุ",
    "note",
    "remark",
    "service_label",
    "service_type",
    "ชื่อบริการ",
    "รายการตรวจ",
}

HISTORY_SHEET_NAME_HINTS = ("history", "screen", "ตรวจ", "pap", "via", "hpv", "icd", "ผล")
ROSTER_SHEET_NAME_HINTS = ("roster", "target", "รายชื่อ", "กลุ่ม", "ทะเบียน")


@dataclass
class ParsedTargetGroupRow:
    source_filename: str
    source_sheet_name: str
    source_sheet_index: int
    row_number: int
    values: dict[str, Any]
    sheet_type: str = TARGET_GROUP_ROSTER
    sheet_warning: str | None = None


@dataclass
class ParsedTargetGroupSheet:
    source_filename: str
    sheet_name: str
    sheet_index: int
    sheet_type: str
    row_count: int
    column_names: list[str] = field(default_factory=list)
    classification_confidence: float | None = None
    notes: str | None = None


@dataclass
class ParsedTargetGroupWorkbook:
    rows: list[ParsedTargetGroupRow]
    sheets: list[ParsedTargetGroupSheet]


@dataclass
class SheetClassification:
    sheet_type: str
    warning_message: str | None = None
    confidence: float | None = None


class ExcelTargetGroupImporter:
    TARGET_GROUP_CERVICAL_COLUMN_MAP = {
        1: "external_person_id",
        2: "hn",
        3: "raw_cid",
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
    def read_rows(cls, path: Path) -> list[ParsedTargetGroupRow]:
        return cls.read_workbook(path).rows

    @classmethod
    def read_workbook(cls, path: Path) -> ParsedTargetGroupWorkbook:
        if path.suffix.lower() == ".csv":
            return cls._read_generic_csv_target_group(path)

        engine = cls._resolve_excel_engine(path)
        workbook = pd.ExcelFile(path, engine=engine)
        rows: list[ParsedTargetGroupRow] = []
        sheets: list[ParsedTargetGroupSheet] = []
        for sheet_index, sheet_name in enumerate(workbook.sheet_names):
            if cls._looks_like_cervical_screening_sheet(workbook, sheet_name):
                cervical_rows = cls._read_cervical_screening_sheet(path, workbook, sheet_name, sheet_index)
                rows.extend(cervical_rows)
                sheets.append(
                    ParsedTargetGroupSheet(
                        source_filename=path.name,
                        sheet_name=sheet_name,
                        sheet_index=sheet_index,
                        sheet_type=MIXED_SHEET,
                        row_count=len(cervical_rows),
                        column_names=list(cls.TARGET_GROUP_CERVICAL_COLUMN_MAP.values()),
                        classification_confidence=0.95,
                        notes="Detected structured cervical screening registry sheet with roster and history fields.",
                    )
                )
                continue

            generic_rows, sheet = cls._read_generic_sheet(path, workbook, sheet_name, sheet_index)
            rows.extend(generic_rows)
            sheets.append(sheet)

        return ParsedTargetGroupWorkbook(rows=rows, sheets=sheets)

    @staticmethod
    def _resolve_excel_engine(path: Path) -> str:
        return "xlrd" if path.suffix.lower() == ".xls" else "openpyxl"

    @classmethod
    def _looks_like_cervical_screening_sheet(cls, workbook: pd.ExcelFile, sheet_name: str) -> bool:
        preview = workbook.parse(sheet_name=sheet_name, header=None, nrows=3)
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
    def _read_cervical_screening_sheet(
        cls,
        path: Path,
        workbook: pd.ExcelFile,
        sheet_name: str,
        sheet_index: int,
    ) -> list[ParsedTargetGroupRow]:
        frame = workbook.parse(sheet_name=sheet_name, header=None)
        title = str(frame.iloc[0, 0]).strip() if pd.notna(frame.iloc[0, 0]) else ""
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
                    source_filename=path.name,
                    source_sheet_name=sheet_name,
                    source_sheet_index=sheet_index,
                    row_number=zero_index + 1,
                    values=mapped,
                    sheet_type=MIXED_SHEET,
                )
            )

        return rows

    @classmethod
    def _read_generic_csv_target_group(cls, path: Path) -> ParsedTargetGroupWorkbook:
        frame = pd.read_csv(path)
        safe_frame = frame.astype(object).where(pd.notnull(frame), None)
        column_names = [str(column) for column in safe_frame.columns]
        classification = cls._classify_sheet("csv", column_names)

        rows: list[ParsedTargetGroupRow] = []
        for zero_index, payload in enumerate(safe_frame.to_dict(orient="records"), start=2):
            rows.append(
                ParsedTargetGroupRow(
                    source_filename=path.name,
                    source_sheet_name="csv",
                    source_sheet_index=0,
                    row_number=zero_index,
                    values=payload,
                    sheet_type=classification.sheet_type,
                    sheet_warning=classification.warning_message,
                )
            )

        return ParsedTargetGroupWorkbook(
            rows=rows,
            sheets=[
                ParsedTargetGroupSheet(
                    source_filename=path.name,
                    sheet_name="csv",
                    sheet_index=0,
                    sheet_type=classification.sheet_type,
                    row_count=len(rows),
                    column_names=column_names,
                    classification_confidence=classification.confidence,
                    notes=classification.warning_message,
                )
            ],
        )

    @classmethod
    def _read_generic_sheet(
        cls,
        path: Path,
        workbook: pd.ExcelFile,
        sheet_name: str,
        sheet_index: int,
    ) -> tuple[list[ParsedTargetGroupRow], ParsedTargetGroupSheet]:
        # dtype=object prevents pandas from converting numeric-looking strings
        # (such as CIDs with leading zeros like "0112000000010") to int64/float64.
        # All normalization (CID, age, date) already handles str/object inputs.
        frame = workbook.parse(sheet_name=sheet_name, dtype=object)
        safe_frame = frame.astype(object).where(pd.notnull(frame), None)
        column_names = [str(column) for column in safe_frame.columns]
        classification = cls._classify_sheet(sheet_name, column_names)
        rows: list[ParsedTargetGroupRow] = []

        for zero_index, payload in enumerate(safe_frame.to_dict(orient="records"), start=2):
            values = dict(payload)
            if classification.warning_message:
                values["parse_warning"] = classification.warning_message
            rows.append(
                ParsedTargetGroupRow(
                    source_filename=path.name,
                    source_sheet_name=sheet_name,
                    source_sheet_index=sheet_index,
                    row_number=zero_index,
                    values=values,
                    sheet_type=classification.sheet_type,
                    sheet_warning=classification.warning_message,
                )
            )

        sheet = ParsedTargetGroupSheet(
            source_filename=path.name,
            sheet_name=sheet_name,
            sheet_index=sheet_index,
            sheet_type=classification.sheet_type,
            row_count=len(rows),
            column_names=column_names,
            classification_confidence=classification.confidence,
            notes=classification.warning_message,
        )
        return rows, sheet

    @classmethod
    def _classify_sheet(cls, sheet_name: str, columns: list[str]) -> SheetClassification:
        normalized_sheet_name = sheet_name.strip().casefold()
        normalized_columns = {str(column).strip().casefold() for column in columns if str(column).strip()}
        person_identity_hints = {column.casefold() for column in PERSON_IDENTITY_COLUMNS}
        roster_context_hints = {column.casefold() for column in ROSTER_CONTEXT_COLUMNS}
        history_hints = {column.casefold() for column in HISTORY_HINT_COLUMNS}

        roster_matches = normalized_columns & roster_context_hints
        history_matches = normalized_columns & history_hints
        has_person_columns = bool(normalized_columns & person_identity_hints)

        if has_person_columns and roster_matches and history_matches:
            return SheetClassification(
                sheet_type=MIXED_SHEET,
                confidence=0.9,
                warning_message="sheet นี้มีทั้งข้อมูลรายชื่อและประวัติบริการ จึงถูกใช้ทั้งในส่วน roster และ history",
            )

        if has_person_columns and history_matches:
            return SheetClassification(
                sheet_type=HISTORY_SHEET,
                confidence=0.85,
                warning_message=None,
            )

        if has_person_columns and roster_matches:
            return SheetClassification(
                sheet_type=ROSTER_SHEET,
                confidence=0.85,
                warning_message=None,
            )

        if any(hint in normalized_sheet_name for hint in HISTORY_SHEET_NAME_HINTS) and has_person_columns:
            return SheetClassification(
                sheet_type=HISTORY_SHEET,
                confidence=0.65,
                warning_message="classify จากชื่อ sheet และโครงสร้างคอลัมน์ ควรตรวจสอบอีกครั้งหากความหมายของคอลัมน์ไม่ตรงตามคาด",
            )

        if any(hint in normalized_sheet_name for hint in ROSTER_SHEET_NAME_HINTS) and has_person_columns:
            return SheetClassification(
                sheet_type=ROSTER_SHEET,
                confidence=0.65,
                warning_message="classify จากชื่อ sheet และโครงสร้างคอลัมน์ ควรตรวจสอบอีกครั้งหากความหมายของคอลัมน์ไม่ตรงตามคาด",
            )

        return SheetClassification(
            sheet_type=UNKNOWN_SHEET,
            confidence=0.2 if normalized_columns else 0.0,
            warning_message=f"sheet '{sheet_name}' ยังจัดประเภทไม่ได้อย่างปลอดภัย จึงเก็บไว้เป็น unknown_sheet และรอตรวจสอบ",
        )

    @classmethod
    def _map_target_group_cervical_row(cls, row: list[Any]) -> dict[str, Any]:
        mapped: dict[str, Any] = {
            "pid": None,
            "citizen_id": None,
            "raw_cid": None,
            "hn": None,
            "full_name": None,
            "birth_date": None,
        }
        for index, key in cls.TARGET_GROUP_CERVICAL_COLUMN_MAP.items():
            mapped[key] = row[index] if index < len(row) and pd.notna(row[index]) else None
        mapped["citizen_id"] = mapped.get("raw_cid")
        mapped["CID"] = mapped.get("raw_cid")
        return mapped


    @staticmethod
    def _is_target_group_data_row(row: dict[str, Any]) -> bool:
        return bool(row.get("citizen_id") or row.get("hn") or row.get("full_name"))
