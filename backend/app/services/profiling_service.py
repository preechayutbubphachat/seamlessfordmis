from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from app.importers.excel_main_history_importer import ExcelMainHistoryImporter
from app.importers.excel_target_group_importer import ExcelTargetGroupImporter
from app.schemas.profiling import (
    DateColumnProfile,
    FileProfile,
    IdentifierQualitySummary,
    ProfilingSummary,
)
from app.services.field_mapping_service import FieldMappingService
from app.utils.files import detect_file_type
from app.utils.text_normalization import (
    DATE_INVALID,
    DATE_MISSING,
    DATE_VALID,
    IDENTIFIER_INVALID,
    IDENTIFIER_MISSING,
    IDENTIFIER_VALID,
    parse_service_date,
)


IMPORTANT_SCREENING_COLUMNS = [
    "raw_person_identifier",
    "hn",
    "full_name",
    "raw_visit_date",
    "raw_service_type",
]
IMPORTANT_TARGET_COLUMNS = [
    "raw_cid",
    "hn",
    "full_name",
    "birth_date",
]
LIKELY_SCREENING_DATE_COLUMNS = ["submitted_date", "raw_visit_date", "visit_date"]
LIKELY_TARGET_DATE_COLUMNS = ["birth_date", "screening_visit_date", "reply_date"]


@dataclass
class _ProfileAccumulator:
    available_columns: set[str]
    important_non_null_counts: Counter[str]
    service_samples: Counter[str]
    anomalies: list[str]
    date_profiles: dict[str, Counter[str]]
    identifier_states: Counter[str]
    normalized_identifiers: list[str]
    looks_like_13_digit_rows: int
    non_null_identifier_rows: int


@dataclass
class _SingleFileProfileResult:
    file_profile: FileProfile
    normalized_identifiers: list[str]


class ProfilingService:
    @classmethod
    def profile_disease_screening_files(cls, paths: list[Path]) -> ProfilingSummary:
        return cls._profile_files(profile_type="disease_screening", paths=paths)

    @classmethod
    def profile_target_group_files(cls, paths: list[Path]) -> ProfilingSummary:
        return cls._profile_files(profile_type="target_group", paths=paths)

    @classmethod
    def _profile_files(cls, profile_type: str, paths: list[Path]) -> ProfilingSummary:
        accumulator = _ProfileAccumulator(
            available_columns=set(),
            important_non_null_counts=Counter(),
            service_samples=Counter(),
            anomalies=[],
            date_profiles={},
            identifier_states=Counter(),
            normalized_identifiers=[],
            looks_like_13_digit_rows=0,
            non_null_identifier_rows=0,
        )
        file_profiles: list[FileProfile] = []
        all_normalized_identifiers: list[str] = []
        total_rows = 0

        for path in paths:
            single_result = cls._profile_single_file(profile_type, path)
            file_profile = single_result.file_profile
            file_profiles.append(file_profile)
            all_normalized_identifiers.extend(single_result.normalized_identifiers)
            total_rows += file_profile.row_count
            accumulator.available_columns.update(file_profile.available_columns)
            accumulator.important_non_null_counts.update(file_profile.important_non_null_counts)
            accumulator.service_samples.update(file_profile.service_type_samples)
            accumulator.anomalies.extend(file_profile.anomalies)
            cls._merge_date_profiles(accumulator.date_profiles, file_profile.date_profiles)
            accumulator.identifier_states.update(
                {
                    IDENTIFIER_VALID: file_profile.identifier_quality.valid_rows,
                    IDENTIFIER_INVALID: file_profile.identifier_quality.invalid_rows,
                    IDENTIFIER_MISSING: file_profile.identifier_quality.missing_rows,
                }
            )
            accumulator.looks_like_13_digit_rows += file_profile.identifier_quality.looks_like_13_digit_rows
            accumulator.non_null_identifier_rows += file_profile.identifier_quality.non_null_rows

        summary = ProfilingSummary(
            profile_type=profile_type,
            generated_at=datetime.now().isoformat(),
            total_files=len(paths),
            total_rows=total_rows,
            available_columns=sorted(accumulator.available_columns),
            important_non_null_counts=dict(accumulator.important_non_null_counts),
            date_profiles=cls._finalize_date_profiles(accumulator.date_profiles, total_rows),
            service_type_samples=[item for item, _ in accumulator.service_samples.most_common(20)],
            identifier_quality=cls._build_identifier_quality_from_counters(
                total_rows=total_rows,
                non_null_rows=accumulator.non_null_identifier_rows,
                valid_rows=accumulator.identifier_states[IDENTIFIER_VALID],
                invalid_rows=accumulator.identifier_states[IDENTIFIER_INVALID],
                missing_rows=accumulator.identifier_states[IDENTIFIER_MISSING],
                looks_like_13_digit_rows=accumulator.looks_like_13_digit_rows,
                normalized_identifiers=all_normalized_identifiers,
            ),
            files=file_profiles,
            anomalies=cls._dedupe(accumulator.anomalies),
            unresolved_questions=cls._build_unresolved_questions(profile_type, file_profiles),
            metadata={"paths_profiled": [str(path.resolve()) for path in paths]},
        )
        return summary

    @classmethod
    def _profile_single_file(cls, profile_type: str, path: Path) -> _SingleFileProfileResult:
        rows = (
            ExcelMainHistoryImporter.read_rows(path)
            if profile_type == "disease_screening"
            else ExcelTargetGroupImporter.read_rows(path)
        )
        accumulator = _ProfileAccumulator(
            available_columns=set(),
            important_non_null_counts=Counter(),
            service_samples=Counter(),
            anomalies=[],
            date_profiles={},
            identifier_states=Counter(),
            normalized_identifiers=[],
            looks_like_13_digit_rows=0,
            non_null_identifier_rows=0,
        )

        for parsed in rows:
            payload = parsed.values
            accumulator.available_columns.update(payload.keys())
            if profile_type == "disease_screening":
                mapped = FieldMappingService.map_disease_screening_row(payload)
                cls._collect_counts(accumulator, payload, IMPORTANT_SCREENING_COLUMNS, LIKELY_SCREENING_DATE_COLUMNS, mapped)
            else:
                mapped = FieldMappingService.map_target_group_row(payload)
                cls._collect_counts(accumulator, payload, IMPORTANT_TARGET_COLUMNS, LIKELY_TARGET_DATE_COLUMNS, mapped)

        identifier_quality = cls._build_identifier_quality_from_counters(
            total_rows=len(rows),
            non_null_rows=accumulator.non_null_identifier_rows,
            valid_rows=accumulator.identifier_states[IDENTIFIER_VALID],
            invalid_rows=accumulator.identifier_states[IDENTIFIER_INVALID],
            missing_rows=accumulator.identifier_states[IDENTIFIER_MISSING],
            looks_like_13_digit_rows=accumulator.looks_like_13_digit_rows,
            normalized_identifiers=accumulator.normalized_identifiers,
        )

        profile = FileProfile(
            file_name=path.name,
            file_type=detect_file_type(path),
            row_count=len(rows),
            available_columns=sorted(accumulator.available_columns),
            important_non_null_counts=dict(accumulator.important_non_null_counts),
            date_profiles=cls._finalize_date_profiles(accumulator.date_profiles, len(rows)),
            service_type_samples=[item for item, _ in accumulator.service_samples.most_common(20)],
            identifier_quality=identifier_quality,
            anomalies=cls._dedupe(accumulator.anomalies),
        )
        return _SingleFileProfileResult(
            file_profile=profile,
            normalized_identifiers=accumulator.normalized_identifiers,
        )

    @staticmethod
    def _collect_counts(
        accumulator: _ProfileAccumulator,
        payload: dict[str, Any],
        important_columns: list[str],
        date_columns: list[str],
        mapped: dict[str, Any],
    ) -> None:
        for column in important_columns:
            raw_value = mapped.get(column) if column in mapped else payload.get(column)
            if raw_value not in (None, ""):
                accumulator.important_non_null_counts[column] += 1

        service_value = mapped.get("raw_service_type")
        if service_value:
            accumulator.service_samples[str(service_value)] += 1

        identifier_value = mapped.get("normalized_person_identifier") or mapped.get("normalized_cid")
        identifier_state = mapped.get("identifier_validation_status") or mapped.get("cid_validation_status")
        if mapped.get("raw_person_identifier") or mapped.get("raw_cid"):
            accumulator.non_null_identifier_rows += 1
        accumulator.identifier_states[identifier_state or IDENTIFIER_MISSING] += 1
        if identifier_value:
            accumulator.normalized_identifiers.append(identifier_value)
        if mapped.get("looks_like_13_digit_identifier") or mapped.get("looks_like_13_digit_cid"):
            accumulator.looks_like_13_digit_rows += 1
        if identifier_state == IDENTIFIER_INVALID:
            accumulator.anomalies.append("พบ identifier ที่ไม่ผ่านกติกา 13 หลักหลัง normalize")

        for column in date_columns:
            date_result = parse_service_date(payload.get(column) if column in payload else mapped.get(column))
            counter = accumulator.date_profiles.setdefault(column, Counter())
            counter[date_result.validation_state] += 1
            if date_result.validation_state == DATE_INVALID:
                accumulator.anomalies.append(f"พบค่าวันที่ที่ parse ไม่ได้ในคอลัมน์ {column}")

    @staticmethod
    def _build_identifier_quality_from_counters(
        *,
        total_rows: int,
        non_null_rows: int,
        valid_rows: int,
        invalid_rows: int,
        missing_rows: int,
        looks_like_13_digit_rows: int,
        normalized_identifiers: list[str],
    ) -> IdentifierQualitySummary:
        counter = Counter(normalized_identifiers)
        duplicate_rows = sum(count for count in counter.values() if count > 1)
        return IdentifierQualitySummary(
            total_rows=total_rows,
            non_null_rows=non_null_rows,
            valid_rows=valid_rows,
            invalid_rows=invalid_rows,
            missing_rows=missing_rows or max(total_rows - non_null_rows, 0),
            looks_like_13_digit_rows=looks_like_13_digit_rows,
            duplicate_normalized_identifier_rows=duplicate_rows,
            distinct_normalized_identifier_count=len(counter),
            valid_percentage=ProfilingService._percentage(valid_rows, total_rows),
            invalid_percentage=ProfilingService._percentage(invalid_rows, total_rows),
            missing_percentage=ProfilingService._percentage(missing_rows or max(total_rows - non_null_rows, 0), total_rows),
            looks_like_13_digit_percentage=ProfilingService._percentage(looks_like_13_digit_rows, total_rows),
            duplicate_rate_percentage=ProfilingService._percentage(duplicate_rows, len(normalized_identifiers)),
        )

    @staticmethod
    def _merge_date_profiles(target: dict[str, Counter[str]], source_profiles: list[DateColumnProfile]) -> None:
        for profile in source_profiles:
            counter = target.setdefault(profile.column_name, Counter())
            counter[DATE_VALID] += profile.valid_rows
            counter[DATE_INVALID] += profile.invalid_rows
            counter[DATE_MISSING] += profile.missing_rows

    @staticmethod
    def _finalize_date_profiles(counters: dict[str, Counter[str]], total_rows: int) -> list[DateColumnProfile]:
        profiles: list[DateColumnProfile] = []
        for column_name, counter in sorted(counters.items()):
            non_null_rows = counter[DATE_VALID] + counter[DATE_INVALID]
            profiles.append(
                DateColumnProfile(
                    column_name=column_name,
                    non_null_rows=non_null_rows,
                    valid_rows=counter[DATE_VALID],
                    invalid_rows=counter[DATE_INVALID],
                    missing_rows=counter[DATE_MISSING] or max(total_rows - non_null_rows, 0),
                    parseable_percentage=ProfilingService._percentage(counter[DATE_VALID], non_null_rows),
                )
            )
        return profiles

    @staticmethod
    def _build_unresolved_questions(profile_type: str, file_profiles: list[FileProfile]) -> list[str]:
        questions: list[str] = []
        if profile_type == "disease_screening":
            questions.append("ต้องยืนยันกับเจ้าของข้อมูลว่าคอลัมน์ VCTID,NAPNumber,PID ใช้เทียบ CID ได้ทุกไฟล์จริงหรือไม่")
        else:
            questions.append("ต้องยืนยันว่าการไม่มี CID ในไฟล์กลุ่มเป้าหมายควรถูก reject ทั้งแถวหรือส่งต่อเป็น needs_review")

        if any(file.identifier_quality.invalid_rows for file in file_profiles):
            questions.append("พบ identifier ที่ไม่เข้าเกณฑ์ 13 หลักหลัง normalize ควรตรวจว่ามี prefix/suffix ทางธุรกิจหรือไม่")
        if any(file.identifier_quality.duplicate_normalized_identifier_rows for file in file_profiles):
            questions.append("พบ normalized identifier ซ้ำ ต้องกำหนดนโยบาย dedupe ใน phase ถัดไป")
        return ProfilingService._dedupe(questions)

    @staticmethod
    def _percentage(numerator: int, denominator: int) -> float:
        if denominator <= 0:
            return 0.0
        return round((numerator / denominator) * 100, 2)

    @staticmethod
    def _dedupe(values: list[str]) -> list[str]:
        seen: set[str] = set()
        output: list[str] = []
        for value in values:
            if value in seen:
                continue
            seen.add(value)
            output.append(value)
        return output

    @staticmethod
    def to_markdown(summary: ProfilingSummary) -> str:
        lines = [
            f"# Profiling Report: {summary.profile_type}",
            "",
            f"- Generated at: {summary.generated_at}",
            f"- Total files: {summary.total_files}",
            f"- Total rows: {summary.total_rows}",
            f"- Available columns: {', '.join(summary.available_columns)}",
            "",
            "## Identifier quality",
            f"- Valid rows: {summary.identifier_quality.valid_rows} ({summary.identifier_quality.valid_percentage}%)",
            f"- Invalid rows: {summary.identifier_quality.invalid_rows} ({summary.identifier_quality.invalid_percentage}%)",
            f"- Missing rows: {summary.identifier_quality.missing_rows} ({summary.identifier_quality.missing_percentage}%)",
            f"- Looks like 13 digits: {summary.identifier_quality.looks_like_13_digit_rows} ({summary.identifier_quality.looks_like_13_digit_percentage}%)",
            f"- Duplicate normalized identifiers: {summary.identifier_quality.duplicate_normalized_identifier_rows} ({summary.identifier_quality.duplicate_rate_percentage}%)",
            "",
            "## Important non-null counts",
        ]
        for key, value in summary.important_non_null_counts.items():
            lines.append(f"- {key}: {value}")
        lines.extend(["", "## Date parseability"])
        for profile in summary.date_profiles:
            lines.append(
                f"- {profile.column_name}: valid={profile.valid_rows}, invalid={profile.invalid_rows}, missing={profile.missing_rows}, parseable={profile.parseable_percentage}%"
            )
        if summary.service_type_samples:
            lines.extend(["", "## Service type samples"])
            for item in summary.service_type_samples:
                lines.append(f"- {item}")
        if summary.anomalies:
            lines.extend(["", "## Detected anomalies"])
            for anomaly in summary.anomalies:
                lines.append(f"- {anomaly}")
        if summary.unresolved_questions:
            lines.extend(["", "## Unresolved questions"])
            for question in summary.unresolved_questions:
                lines.append(f"- {question}")
        return "\n".join(lines) + "\n"
