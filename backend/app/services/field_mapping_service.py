from app.utils.text_normalization import (
    normalize_age,
    normalize_identifier,
    normalize_name,
    normalize_service_key,
    normalize_sex,
    normalize_text,
    parse_service_date,
)

# ---------------------------------------------------------------------------
# Thai service-label slug -> canonical service key lookup table
#
# normalize_service_key() is a generic slugifier with no domain vocabulary.
# History sheets in target-group workbooks often carry Thai service labels
# such as "คัดกรองมะเร็งปากมดลูก" which normalise to their Thai slug and
# never match the English canonical key "cervical_screen" the result-
# generation engine searches for.
#
# This lookup table is the single authoritative mapping from those slugs to
# the canonical service keys used throughout the system.  Add new entries
# whenever a new disease or service is introduced in disease_mapping_seed.
# ---------------------------------------------------------------------------
_THAI_SERVICE_SLUG_TO_CANONICAL: dict[str, str] = {
    # Cervical cancer screening
    "คัดกรองมะเร็งปากมดลูก": "cervical_screen",
    "ตรวจมะเร็งปากมดลูก": "cervical_screen",
    "ตรวจคัดกรองมะเร็งปากมดลูก": "cervical_screen",
    "มะเร็งปากมดลูก": "cervical_screen",
    "คัดกรองมะเร็ง": "cervical_screen",
    "z124": "cervical_screen",
    "z12_4": "cervical_screen",
    # Pap smear
    "papsmear": "pap_smear",
    "pap_smear": "pap_smear",
    # HPV
    "hpv": "hpv",
    "hpv_screen": "hpv_screen",
    # VIA
    "via": "via",
    # Diabetes
    "เบาหวาน": "dm",
    "คัดกรองเบาหวาน": "dm",
    "dm": "dm",
    "ตรวจน้ำตาล": "dm_screen_fpg",
    "ตรวจน้ำตาล_fpg": "dm_screen_fpg",
    "fpg": "dm_screen_fpg",
    "dm_screen_fpg": "dm_screen_fpg",
    # Hypertension
    "ความดัน": "ht",
    "ความดันโลหิตสูง": "ht",
    "ht": "ht",
    "hypertension": "ht",
    # CKD
    "ไตเรื้อรัง": "ckd",
    "โรคไตเรื้อรัง": "ckd",
    "ckd": "ckd",
    # Hepatitis
    "ไวรัสตับอักเสบ_บี": "hep_b_screen",
    "hep_b_screen": "hep_b_screen",
    "ไวรัสตับอักเสบ_ซี": "hep_c_screen",
    "hep_c_screen": "hep_c_screen",
}

# human-readable comment for maintainers (slugs above are unicode escapes of):
# "คัดกรองมะเร็งปากมดลูก" -> cervical_screen
# "ตรวจมะเร็งปากมดลูก"   -> cervical_screen
# "ตรวจคัดกรองมะเร็งปากมดลูก" -> cervical_screen
# "มะเร็งปากมดลูก"       -> cervical_screen
# "คัดกรองมะเร็ง"        -> cervical_screen
# "เบาหวาน"              -> dm
# "คัดกรองเบาหวาน"       -> dm
# "ตรวจน้ำตาล"           -> dm_screen_fpg
# "ความดัน"              -> ht
# "ความดันโลหิตสูง"       -> ht
# "ไตเรื้อรัง"            -> ckd
# "โรคไตเรื้อรัง"         -> ckd
# "ไวรัสตับอักเสบ_บี"    -> hep_b_screen
# "ไวรัสตับอักเสบ_ซี"    -> hep_c_screen


def _canonical_service_key(raw_slug: str | None) -> str | None:
    """Return the canonical service key for *raw_slug*, falling back to
    the slug itself when no mapping exists.

    This is the single resolution point that converts Thai-language service
    labels normalised by ``normalize_service_key()`` into the canonical keys
    used by the disease mapping engine and result generation.
    """
    if not raw_slug:
        return raw_slug
    return _THAI_SERVICE_SLUG_TO_CANONICAL.get(raw_slug, raw_slug)


class FieldMappingService:
    """Central mapping layer for reusable import pipelines."""

    @staticmethod
    def map_disease_screening_row(payload: dict) -> dict:
        identifier = normalize_identifier(
            payload.get("raw_person_identifier")
            or payload.get("person_identifier")
            or payload.get("VCTID,NAPNumber,PID")
            or payload.get("vctid,napnumber,pid")
            or payload.get("pid")
        )
        service = normalize_service_key(
            payload.get("raw_service_type")
            or payload.get("service_type")
            or payload.get("service_item_name")
            or payload.get("diagnosis_name")
            or payload.get("disease_name")
        )
        visit_date = parse_service_date(
            payload.get("raw_visit_date")
            or payload.get("visit_date")
            or payload.get("service_date")
        )
        full_name = payload.get("full_name") or payload.get("ชื่อ-สกุล") or payload.get("ชื่อผู้ป่วย")

        return {
            "raw_person_identifier": identifier.raw_value,
            "normalized_person_identifier": identifier.normalized_value,
            "identifier_validation_status": identifier.validation_state,
            "looks_like_13_digit_identifier": identifier.looks_like_13_digit,
            "raw_service_type": service.raw_value,
            "normalized_service_key": service.normalized_value,
            "service_validation_status": service.validation_state,
            "raw_visit_date": visit_date.raw_value,
            "normalized_visit_date": visit_date.normalized_value,
            "date_validation_status": visit_date.validation_state,
            "raw_full_name": normalize_text(full_name),
            "normalized_full_name": normalize_name(full_name),
            "raw_hcode": normalize_text(payload.get("hcode") or payload.get("hmain_op")),
            "raw_transaction_id": normalize_text(payload.get("transaction_id") or payload.get("trans_id")),
            "raw_rep_no": normalize_text(payload.get("rep_no")),
            "raw_hn": normalize_text(payload.get("hn") or payload.get("HN")),
            "normalized_hn": normalize_text(payload.get("hn") or payload.get("HN")),
            "raw_diagnosis_code": normalize_text(payload.get("diagnosis_code") or payload.get("icd10")),
            "raw_department": normalize_text(payload.get("department")),
            "raw_doctor_name": normalize_text(payload.get("doctor_name")),
            "normalized_pid": identifier.normalized_value,
            "normalized_diagnosis_name": service.raw_value,
            "normalized_disease_key": service.normalized_value,
        }

    @staticmethod
    def map_target_group_row(payload: dict) -> dict:
        cid = normalize_identifier(
            payload.get("raw_cid")
            or payload.get("cid")
            or payload.get("CID")
            or payload.get("citizen_id")
        )
        age = normalize_age(payload.get("raw_age") or payload.get("age") or payload.get("age_text") or payload.get("อายุ"))
        sex = normalize_sex(payload.get("raw_sex") or payload.get("sex") or payload.get("เพศ"))
        birth_date = parse_service_date(payload.get("birth_date") or payload.get("วันเกิด"))
        full_name = payload.get("full_name") or payload.get("ชื่อผู้ป่วย") or payload.get("name")
        hn = payload.get("hn") or payload.get("HN")
        history_context = FieldMappingService._extract_target_history_context(payload)

        return {
            "raw_cid": cid.raw_value,
            "normalized_cid": cid.normalized_value,
            "cid_validation_status": cid.validation_state,
            "looks_like_13_digit_cid": cid.looks_like_13_digit,
            "raw_full_name": normalize_text(full_name),
            "normalized_full_name": normalize_name(full_name),
            "raw_age": age.raw_value,
            "normalized_age": age.normalized_value,
            "raw_sex": sex.raw_value,
            "normalized_sex": sex.normalized_value,
            "raw_hn": normalize_text(hn),
            "normalized_hn": normalize_text(hn),
            "raw_birth_date": birth_date.raw_value,
            "normalized_birth_date": birth_date.normalized_value,
            "normalized_citizen_id": cid.normalized_value,
            "raw_target_history_labels": history_context["raw_target_history_labels"],
            "normalized_target_history_service_keys": history_context["normalized_target_history_service_keys"],
            "raw_target_history_note": history_context["raw_target_history_note"],
            "raw_target_history_last_visit_date": history_context["raw_target_history_last_visit_date"],
            "normalized_target_history_last_visit_date": history_context["normalized_target_history_last_visit_date"],
        }

    @staticmethod
    def map_target_group_history_row(payload: dict) -> dict:
        cid = normalize_identifier(
            payload.get("raw_cid")
            or payload.get("cid")
            or payload.get("CID")
            or payload.get("citizen_id")
        )
        full_name = (
            payload.get("full_name")
            or payload.get("ชื่อผู้ป่วย")
            or payload.get("ชื่อ-สกุล")
            or payload.get("name")
        )
        birth_date = parse_service_date(
            payload.get("raw_birth_date") or payload.get("birth_date") or payload.get("วันเกิด")
        )
        raw_address = normalize_text(
            payload.get("raw_address") or payload.get("address") or payload.get("ที่อยู่")
        )
        visit_date = parse_service_date(
            payload.get("raw_visit_date")
            or payload.get("visit_date")
            or payload.get("screening_visit_date")
            or payload.get("วันที่ตรวจ")
            or payload.get("วันที่รับบริการ")
            or payload.get("reply_date")
        )
        derived_service = FieldMappingService._extract_target_group_history_service(payload)
        return {
            "raw_cid": cid.raw_value,
            "normalized_cid": cid.normalized_value,
            "identifier_validation_status": cid.validation_state,
            "raw_full_name": normalize_text(full_name),
            "normalized_full_name": normalize_name(full_name),
            "raw_birth_date": birth_date.raw_value,
            "normalized_birth_date": birth_date.normalized_value,
            "raw_address": raw_address,
            "normalized_address": normalize_text(raw_address),
            "raw_service_label": normalize_text(
                payload.get("raw_service_label")
                or payload.get("service_label")
                or payload.get("service_type")
                or payload.get("ชื่อบริการ")
                or payload.get("รายการตรวจ")
            ),
            "raw_service_type": derived_service["raw_service_type"],
            "normalized_service_key": derived_service["normalized_service_key"],
            "service_validation_status": derived_service["service_validation_status"],
            "raw_visit_date": visit_date.raw_value,
            "normalized_visit_date": visit_date.normalized_value,
            "date_validation_status": visit_date.validation_state,
            "raw_icd10": normalize_text(
                payload.get("raw_icd10") or payload.get("icd10") or payload.get("ICD10")
            ),
            "raw_result": derived_service["raw_result"],
            "raw_hpv": normalize_text(
                payload.get("raw_hpv")
                or payload.get("hpv")
                or payload.get("hpv_result")
                or payload.get("HPV")
            ),
            "raw_hospital": normalize_text(
                payload.get("raw_hospital")
                or payload.get("hospital_name")
                or payload.get("สถานพยาบาล")
            ),
            "raw_doctor": normalize_text(
                payload.get("raw_doctor")
                or payload.get("doctor_name")
                or payload.get("ชื่อแพทย์")
            ),
            "raw_note": normalize_text(
                payload.get("raw_note")
                or payload.get("note")
                or payload.get("remark")
                or payload.get("หมายเหตุ")
                or payload.get("cc")
            ),
            "warning_message": derived_service["warning_message"],
        }

    @staticmethod
    def _extract_target_history_context(payload: dict) -> dict:
        history_labels: list[str] = []
        normalized_keys: list[str] = []

        field_to_label = {
            "pap_smear_result": "Pap smear",
            "via_result": "VIA",
            "hpv_result": "HPV",
            "other_method_result": "Other method",
            "service_label": "Service",
            "treatment_history": "Treatment history",
        }
        field_to_key = {
            "pap_smear_result": "pap_smear",
            "via_result": "via",
            "hpv_result": "hpv",
            "other_method_result": "other_method",
        }

        for field, label in field_to_label.items():
            raw_value = normalize_text(payload.get(field))
            if not raw_value:
                continue
            history_labels.append(f"{label}: {raw_value}")
            normalized_key = field_to_key.get(field)
            if normalized_key:
                normalized_keys.append(normalized_key)
                normalized_keys.append("cervical_screen")
                continue
            # Apply canonical remapping so Thai service labels resolve correctly
            service_key = _canonical_service_key(normalize_service_key(raw_value).normalized_value)
            if service_key:
                normalized_keys.append(service_key)

        raw_note = normalize_text(
            payload.get("note") or payload.get("remark") or payload.get("cc")
        )
        last_visit = parse_service_date(
            payload.get("screening_visit_date")
            or payload.get("last_visit_date")
            or payload.get("reply_date")
        )

        return {
            "raw_target_history_labels": "; ".join(history_labels) or None,
            "normalized_target_history_service_keys": sorted(set(normalized_keys)) or None,
            "raw_target_history_note": raw_note,
            "raw_target_history_last_visit_date": last_visit.raw_value,
            "normalized_target_history_last_visit_date": last_visit.normalized_value,
        }

    @staticmethod
    def _extract_target_group_history_service(payload: dict) -> dict:
        explicit_service = (
            payload.get("raw_service_type")
            or payload.get("service_type")
            or payload.get("service_label")
            or payload.get("ชื่อบริการ")
            or payload.get("รายการตรวจ")
        )
        explicit_service_result = normalize_service_key(explicit_service)
        if explicit_service_result.normalized_value:
            # Remap Thai-language slugs to their canonical service key so that
            # history rows from target-group files match the keys used in the
            # result-generation engine.
            canonical_key = _canonical_service_key(explicit_service_result.normalized_value)
            raw_result = normalize_text(
                payload.get("raw_result")
                or payload.get("result")
                or payload.get("ผลการตรวจ")
                or payload.get("pap_smear_result")
                or payload.get("via_result")
                or payload.get("hpv_result")
            )
            return {
                "raw_service_type": explicit_service_result.raw_value,
                "normalized_service_key": canonical_key,
                "service_validation_status": explicit_service_result.validation_state,
                "raw_result": raw_result,
                "warning_message": None,
            }

        cervical_indicators = []
        for field in ("pap_smear_result", "via_result", "hpv_result", "other_method_result"):
            raw_value = normalize_text(payload.get(field))
            if raw_value:
                cervical_indicators.append(f"{field}={raw_value}")

        if cervical_indicators:
            raw_result = "; ".join(cervical_indicators)
            warning_message = (
                "พบผลตรวจหลายช่องในแถวเดียว ระบบใช้ service key แบบรวม cervical_screen"
                " เพื่อให้คัดกรองได้อย่างปลอดภัย"
            )
            return {
                "raw_service_type": "คัดกรองมะเร็งปากมดลูก",
                "normalized_service_key": "cervical_screen",
                "service_validation_status": "known_service",
                "raw_result": raw_result,
                "warning_message": warning_message if len(cervical_indicators) > 1 else None,
            }

        icd10 = normalize_text(payload.get("icd10") or payload.get("ICD10"))
        if icd10:
            normalized = normalize_service_key(icd10)
            # Also remap ICD-10 slugs (e.g. "z124" -> "cervical_screen")
            icd_canonical_key = _canonical_service_key(normalized.normalized_value)
            return {
                "raw_service_type": icd10,
                "normalized_service_key": icd_canonical_key,
                "service_validation_status": normalized.validation_state,
                "raw_result": normalize_text(payload.get("result") or payload.get("ผลการตรวจ")),
                "warning_message": "ใช้ ICD10 เป็นต้นทางของ service key ในแถวประวัติจากไฟล์กลุ่มเป้าหมาย",
            }

        return {
            "raw_service_type": None,
            "normalized_service_key": None,
            "service_validation_status": "missing_service",
            "raw_result": normalize_text(payload.get("result") or payload.get("ผลการตรวจ")),
            "warning_message": "ไม่พบ service type ที่ชัดเจนใน sheet ประวัติจากไฟล์กลุ่มเป้าหมาย",
        }
