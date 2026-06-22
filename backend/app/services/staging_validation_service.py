from app.schemas.common import ValidationIssue
from app.services.field_mapping_service import FieldMappingService
from app.utils.validators import is_known_service_state, is_valid_date_state, is_valid_identifier_state


class StagingValidationService:
    @staticmethod
    def validate_main_history_row(row_no: int, payload: dict) -> tuple[dict, list[ValidationIssue]]:
        normalized = FieldMappingService.map_disease_screening_row(payload)
        normalized.update(
            {
                "pid": normalized["normalized_person_identifier"],
                "citizen_id": None,
                "hn": normalized["normalized_hn"],
                "full_name": normalized["normalized_full_name"],
                "birth_date": None,
                "visit_date": normalized["normalized_visit_date"],
                "diagnosis_code": normalized["raw_diagnosis_code"],
                "diagnosis_name": normalized["raw_service_type"],
                "department": normalized["raw_department"],
                "doctor_name": normalized["raw_doctor_name"],
            }
        )

        issues: list[ValidationIssue] = []
        if not is_valid_identifier_state(normalized["identifier_validation_status"]):
            issues.append(
                ValidationIssue(
                    row_no=row_no,
                    field="raw_person_identifier",
                    message="VCTID,NAPNumber,PID ต้อง normalize ได้เป็นรหัส 13 หลักก่อนใช้ใน phase ถัดไป",
                )
            )
        if not is_valid_date_state(normalized["date_validation_status"]):
            issues.append(
                ValidationIssue(
                    row_no=row_no,
                    field="raw_visit_date",
                    message="ไม่พบวันที่รับบริการที่ parse ได้",
                )
            )
        if not is_known_service_state(normalized["service_validation_status"]):
            issues.append(
                ValidationIssue(
                    row_no=row_no,
                    field="raw_service_type",
                    message="ไม่พบรายการบริการ/การตรวจที่ใช้สร้าง normalized service key",
                )
            )
        return normalized, issues

    @staticmethod
    def validate_target_group_row(row_no: int, payload: dict) -> tuple[dict, list[ValidationIssue]]:
        normalized = FieldMappingService.map_target_group_row(payload)
        normalized.update(
            {
                "pid": None,
                "citizen_id": normalized["normalized_cid"],
                "hn": normalized["normalized_hn"],
                "full_name": normalized["normalized_full_name"],
                "birth_date": normalized["normalized_birth_date"],
            }
        )

        issues: list[ValidationIssue] = []
        if not is_valid_identifier_state(normalized["cid_validation_status"]):
            issues.append(
                ValidationIssue(
                    row_no=row_no,
                    field="raw_cid",
                    message="CID ต้อง normalize ได้เป็นรหัส 13 หลักสำหรับ MVP matching",
                )
            )
        return normalized, issues

    @staticmethod
    def validate_target_group_history_row(row_no: int, payload: dict) -> tuple[dict, list[ValidationIssue]]:
        normalized = FieldMappingService.map_target_group_history_row(payload)
        issues: list[ValidationIssue] = []

        if not normalized["normalized_cid"] and not normalized["normalized_full_name"]:
            issues.append(
                ValidationIssue(
                    row_no=row_no,
                    field="identity",
                    message="sheet ประวัติจากไฟล์กลุ่มเป้าหมายต้องมี CID หรือชื่อ-สกุลที่ใช้ติดตามได้อย่างน้อย 1 ค่า",
                )
            )

        if not is_valid_date_state(normalized["date_validation_status"]):
            issues.append(
                ValidationIssue(
                    row_no=row_no,
                    field="raw_visit_date",
                    message="ไม่พบวันที่ตรวจ/รับบริการที่ parse ได้ใน sheet ประวัติจากไฟล์กลุ่มเป้าหมาย",
                )
            )

        if not is_known_service_state(normalized["service_validation_status"]):
            issues.append(
                ValidationIssue(
                    row_no=row_no,
                    field="raw_service_type",
                    message="ไม่พบ service key ที่ชัดเจนใน sheet ประวัติจากไฟล์กลุ่มเป้าหมาย",
                )
            )

        return normalized, issues
