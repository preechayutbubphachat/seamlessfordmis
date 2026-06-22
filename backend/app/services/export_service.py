from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.disease_mapping import DiseaseMapping
from app.models.target_group_job import TargetGroupJob
from app.schemas.common import AuditLogCreate
from app.schemas.result import GroupResultRowResponse, GroupResultsResponse
from app.services.audit_log_service import AuditLogService
from app.services.result_generation_service import ResultGenerationService


@dataclass
class ExportArtifact:
    path: Path
    filename: str
    media_type: str


@dataclass
class ExportBundle:
    group_id: UUID
    group_name: str
    results: GroupResultsResponse
    selected_service_labels: list[str]


class ExportService:
    XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    CSV_MEDIA_TYPE = "text/csv; charset=utf-8"

    @staticmethod
    def export_group_results(
        db: Session,
        group_id: UUID,
        export_format: str = "xlsx",
        selected_service_keys: list[str] | None = None,
        actor: str = "system",
    ) -> ExportArtifact:
        normalized_format = export_format.strip().lower()
        if normalized_format not in {"xlsx", "csv"}:
            raise ValueError("รองรับเฉพาะการ export แบบ xlsx หรือ csv")

        bundle = ExportService.build_export_bundle(db, group_id, selected_service_keys)
        export_dir = settings.source_data_dir / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        filename = ExportService._build_filename(bundle.group_name, group_id, normalized_format)
        export_path = export_dir / filename

        if normalized_format == "xlsx":
            ExportService._write_excel_report(bundle, export_path)
            media_type = ExportService.XLSX_MEDIA_TYPE
        else:
            ExportService._write_csv_report(bundle, export_path)
            media_type = ExportService.CSV_MEDIA_TYPE

        AuditLogService.create(
            db,
            AuditLogCreate(
                actor=actor,
                action="export_group_results",
                entity_type="target_group_jobs",
                entity_id=str(group_id),
                new_value_json={
                    "format": normalized_format,
                    "export_path": str(export_path.resolve()),
                    "row_count": len(bundle.results.results),
                    "selected_service_keys": bundle.results.summary.selected_service_keys,
                },
            ),
        )
        db.commit()
        return ExportArtifact(
            path=export_path.resolve(),
            filename=filename,
            media_type=media_type,
        )

    @staticmethod
    def build_export_bundle(
        db: Session,
        group_id: UUID,
        selected_service_keys: list[str] | None = None,
    ) -> ExportBundle:
        job = db.scalar(select(TargetGroupJob).where(TargetGroupJob.id == group_id))
        if job is None:
            raise ValueError("ไม่พบ target group ที่ต้องการ export")

        results = ResultGenerationService.get_results(db, group_id, include_all=True)
        if not results.results:
            raise ValueError("ยังไม่มีผลลัพธ์สำหรับ export กรุณาสร้างผลลัพธ์ก่อน")

        normalized_selected_keys = sorted({key.strip() for key in (selected_service_keys or []) if key and key.strip()})
        if normalized_selected_keys and normalized_selected_keys != results.summary.selected_service_keys:
            raise ValueError("รายการโรคหรือบริการที่เลือกไม่ตรงกับผลลัพธ์ล่าสุด กรุณาสร้างผลลัพธ์ใหม่ก่อน export")

        mapping_rows = db.scalars(
            select(DiseaseMapping).where(DiseaseMapping.normalized_key.in_(results.summary.selected_service_keys))
        ).all()
        labels_by_key = {row.normalized_key: row.normalized_label for row in mapping_rows}
        selected_service_labels = [labels_by_key.get(key, key) for key in results.summary.selected_service_keys]

        return ExportBundle(
            group_id=group_id,
            group_name=job.group_name,
            results=results,
            selected_service_labels=selected_service_labels,
        )

    @staticmethod
    def _build_filename(group_name: str, group_id: UUID, export_format: str) -> str:
        safe_group_name = "".join(char if char.isalnum() else "-" for char in group_name.strip()).strip("-") or "target-group"
        safe_group_name = safe_group_name[:40]
        date_label = pd.Timestamp.now().strftime("%Y%m%d")
        return f"target-group-{safe_group_name}-{group_id}-{date_label}.{export_format}"

    @staticmethod
    def _write_excel_report(bundle: ExportBundle, export_path: Path) -> None:
        summary_frame = pd.DataFrame(ExportService._summary_rows(bundle))
        results_frame = pd.DataFrame(ExportService._person_rows(bundle))
        breakdown_frame = pd.DataFrame(ExportService._service_breakdown_rows(bundle))

        with pd.ExcelWriter(export_path, engine="openpyxl") as writer:
            summary_frame.to_excel(writer, sheet_name="Summary", index=False)
            results_frame.to_excel(writer, sheet_name="Person Results", index=False)
            if not breakdown_frame.empty:
                breakdown_frame.to_excel(writer, sheet_name="Service Breakdown", index=False)

    @staticmethod
    def _write_csv_report(bundle: ExportBundle, export_path: Path) -> None:
        pd.DataFrame(ExportService._person_rows(bundle, include_context_columns=True)).to_csv(
            export_path,
            index=False,
            encoding="utf-8-sig",
        )

    @staticmethod
    def _summary_rows(bundle: ExportBundle) -> list[dict[str, str | int | float | None]]:
        summary = bundle.results.summary
        selected_keys = ", ".join(summary.selected_service_keys)
        selected_labels = ", ".join(bundle.selected_service_labels)
        return [
            {"รายการ": "ชื่อกลุ่มเป้าหมาย", "ค่า": bundle.group_name},
            {"รายการ": "รหัสกลุ่ม", "ค่า": str(bundle.group_id)},
            {"รายการ": "วันที่สร้างรายงาน", "ค่า": summary.generated_at.isoformat() if summary.generated_at else None},
            {"รายการ": "โรค/บริการที่เลือก (key)", "ค่า": selected_keys},
            {"รายการ": "โรค/บริการที่เลือก", "ค่า": selected_labels},
            {"รายการ": "จำนวนกลุ่มเป้าหมายทั้งหมด", "ค่า": summary.total_target_people},
            {"รายการ": "จำนวนที่มีประวัติในรายการที่เลือก", "ค่า": summary.people_with_selected_history},
            {"รายการ": "จำนวนที่ไม่พบประวัติในรายการที่เลือก", "ค่า": summary.people_without_selected_history},
            {"รายการ": "จำนวนตัวระบุไม่ถูกต้อง / ไม่มีข้อมูลตัวระบุ", "ค่า": summary.invalid_identifier_people},
            {"รายการ": "Coverage (%)", "ค่า": summary.coverage_percent},
            {"รายการ": "ตัวหารที่ใช้คำนวณ coverage", "ค่า": summary.coverage_denominator},
            {"รายการ": "จำนวนคนในตัวหาร", "ค่า": summary.coverage_denominator_people},
        ]

    @staticmethod
    def _person_rows(
        bundle: ExportBundle,
        include_context_columns: bool = False,
    ) -> list[dict[str, str | int | float | None]]:
        base_rows: list[dict[str, str | int | float | None]] = []
        selected_labels = ", ".join(bundle.selected_service_labels)
        for index, row in enumerate(bundle.results.results, start=1):
            export_row: dict[str, str | int | float | None] = {
                "ลำดับ": index,
                "CID / ตัวระบุ": row.normalized_cid,
                "ชื่อ-สกุล": row.full_name,
                "อายุ": row.age,
                "เพศ": row.sex,
                "สถานะผลลัพธ์": ExportService._result_category_label(row.result_category),
                "แหล่งหลักฐาน": ExportService._evidence_source_label(row),
                "จำนวนครั้งที่พบ": row.matching_record_count,
                "วันที่ล่าสุด": row.last_visit_date.isoformat() if row.last_visit_date else None,
                "ผ่านมาแล้วกี่วัน": row.days_since_last_visit,
                "ผ่านมาแล้วกี่ปี": row.years_since_last_visit,
                "หมายเหตุ": row.warning_message,
            }
            if include_context_columns:
                export_row = {
                    "รหัสกลุ่ม": str(bundle.group_id),
                    "ชื่อกลุ่มเป้าหมาย": bundle.group_name,
                    "วันที่สร้างรายงาน": bundle.results.summary.generated_at.isoformat() if bundle.results.summary.generated_at else None,
                    "โรค/บริการที่เลือก": selected_labels,
                    "Coverage (%)": bundle.results.summary.coverage_percent,
                    **export_row,
                }
            base_rows.append(export_row)
        return base_rows

    @staticmethod
    def _service_breakdown_rows(bundle: ExportBundle) -> list[dict[str, str | int]]:
        labels_by_key = dict(zip(bundle.results.summary.selected_service_keys, bundle.selected_service_labels))
        return [
            {
                "selected_service_key": item.selected_service_key,
                "โรค/บริการ": labels_by_key.get(item.selected_service_key, item.selected_service_key),
                "จำนวนคนที่พบ": item.distinct_people_count,
                "จำนวนรายการที่พบ": item.matching_record_count,
            }
            for item in bundle.results.breakdown
        ]

    @staticmethod
    def _result_category_label(category: str) -> str:
        mapping = {
            "has_selected_history": "พบประวัติในรายการที่เลือก",
            "no_selected_history": "ไม่พบประวัติในรายการที่เลือก",
            # Evidence-source categories (must match result classification)
            "both_sources": "พบประวัติทั้งสองแหล่ง",
            "screening_db_only": "พบประวัติในฐานข้อมูลการตรวจโรค",
            "target_group_file_only": "พบประวัติจากไฟล์กลุ่มเป้าหมาย",
            "no_history_found": "ยังไม่พบประวัติ",
            "invalid_identifier": "ตัวระบุไม่ถูกต้อง",
            "missing_identifier": "ไม่มีข้อมูลตัวระบุ",
            "insufficient_identity_data": "ข้อมูลตัวตนไม่เพียงพอ",
            "review_required_identity": "ต้องตรวจสอบตัวตน",
            "non_thai_nationality": "ไม่ใช่สัญชาติไทย",
            "outside_target_scope": "นอกขอบเขตกลุ่มเป้าหมาย",
            "needs_review": "ต้องตรวจสอบ",
        }
        return mapping.get(category, category)

    @staticmethod
    def _evidence_source_label(row) -> str:  # noqa: ANN001
        source = getattr(row, "latest_relevant_source_type", None) or getattr(row, "last_relevant_source", None)
        return {
            "screening_db": "ฐานข้อมูลการตรวจโรค",
            "target_group_file": "ไฟล์กลุ่มเป้าหมาย",
        }.get(source or "", "-")
