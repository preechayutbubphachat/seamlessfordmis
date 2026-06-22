from typing import Any

from app.schemas.common import ValidationIssue
from app.utils.normalizers import normalize_identifier, normalize_name, normalize_text, parse_date


class ValidationService:
    @staticmethod
    def _pick_value(row: dict[str, Any], *keys: str) -> Any:
        for key in keys:
            if key in row and row.get(key) not in (None, ""):
                return row.get(key)
        return None

    @staticmethod
    def validate_history_row(row_number: int, row: dict[str, Any]) -> tuple[dict[str, Any], list[ValidationIssue]]:
        pid = normalize_identifier(row.get("pid"))
        citizen_id = normalize_identifier(row.get("citizen_id"))
        hn = normalize_identifier(row.get("hn"))
        full_name = normalize_text(row.get("full_name"))
        birth_date = parse_date(row.get("birth_date"))
        visit_date = parse_date(row.get("visit_date"))
        diagnosis_code = normalize_identifier(row.get("diagnosis_code"))
        disease_name_raw = normalize_text(row.get("disease_name_raw") or row.get("service_item_name"))
        encounter_type = normalize_text(row.get("coverage_type"))
        provider_name = normalize_text(row.get("hsend"))

        issues: list[ValidationIssue] = []
        if not any([pid, citizen_id, hn, full_name]):
            issues.append(ValidationIssue(row_number=row_number, field="identifier", message="At least one patient identifier is required"))
        if not visit_date:
            issues.append(ValidationIssue(row_number=row_number, field="visit_date", message="Visit date is required"))
        if not any([diagnosis_code, disease_name_raw]):
            issues.append(ValidationIssue(row_number=row_number, field="diagnosis", message="Diagnosis code or disease name is required"))

        normalized = {
            "pid": pid,
            "citizen_id": citizen_id,
            "hn": hn,
            "full_name": full_name,
            "normalized_name": normalize_name(full_name),
            "birth_date": birth_date,
            "visit_date": visit_date,
            "diagnosis_code": diagnosis_code,
            "disease_name_raw": disease_name_raw,
            "encounter_type": encounter_type,
            "provider_name": provider_name,
            "claim_status": normalize_text(row.get("claim_status")),
            "rep_no": normalize_text(row.get("rep_no")),
            "trans_id": normalize_text(row.get("trans_id")),
            "an": normalize_identifier(row.get("an")),
            "submitted_date": parse_date(row.get("submitted_date")),
        }
        return normalized, issues

    @staticmethod
    def validate_target_group_row(row_number: int, row: dict[str, Any]) -> tuple[dict[str, Any], list[ValidationIssue]]:
        pid = normalize_identifier(ValidationService._pick_value(row, "pid", "PID"))
        citizen_id = normalize_identifier(ValidationService._pick_value(row, "citizen_id", "cid", "CID"))
        hn = normalize_identifier(ValidationService._pick_value(row, "hn", "HN"))
        full_name = normalize_text(ValidationService._pick_value(row, "full_name", "ชื่อผู้ป่วย", "name", "NAME"))
        birth_date = parse_date(ValidationService._pick_value(row, "birth_date", "วันเกิด", "dob", "DOB"))

        issues: list[ValidationIssue] = []
        if not any([pid, citizen_id, hn, full_name]):
            issues.append(ValidationIssue(row_number=row_number, field="identifier", message="Target row requires PID, citizen ID, HN, or full name"))
        if full_name and not any([pid, citizen_id, hn]) and not birth_date:
            issues.append(ValidationIssue(row_number=row_number, field="birth_date", message="Birth date is required when matching by name"))

        normalized = {
            "pid": pid,
            "citizen_id": citizen_id,
            "hn": hn,
            "full_name": full_name,
            "birth_date": birth_date,
        }
        return normalized, issues
