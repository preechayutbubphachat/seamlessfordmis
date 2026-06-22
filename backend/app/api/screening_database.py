"""
API endpoints for the disease screening database dashboard.

Safety notes:
- stage-upload writes files to the configured source data directory only.
- database import still requires POST /api/system/sync-disease-screening-database.
- source downloads are limited to files inside source_data_dir.
- reports contain import/source-file metadata, not patient-level rows.
"""

import csv
import io
import logging
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.dependencies import get_db
from app.models.import_job import ImportJob
from app.models.source_file import SourceFile
from app.schemas.common import SourceFileResponse
from app.schemas.screening_database import (
    ImportJobDetailResponse,
    ImportJobListResponse,
    ImportJobSummaryResponse,
    StageUploadResponse,
)

router = APIRouter(prefix="/api/screening-database", tags=["screening-database"])
logger = logging.getLogger(__name__)

_ALLOWED_EXTENSIONS: frozenset[str] = frozenset({".xlsx", ".xls", ".csv", ".pdf"})
_MAX_FILE_SIZE_BYTES: int = 200 * 1024 * 1024

_EXT_TO_TYPE: dict[str, str] = {
    ".xlsx": "excel",
    ".xls": "excel",
    ".csv": "csv",
    ".pdf": "pdf",
}


def _detect_file_type(filename: str) -> str:
    return _EXT_TO_TYPE.get(Path(filename).suffix.lower(), "unknown")


def _job_to_summary(job: ImportJob) -> ImportJobSummaryResponse:
    return ImportJobSummaryResponse(
        import_id=str(job.id),
        status=job.status,
        file_name=job.source_file_name,
        file_type=_detect_file_type(job.source_file_name),
        file_size=job.source_file_size,
        detected_rows=job.total_rows,
        success_rows=job.success_rows,
        failed_rows=job.failed_rows,
        validation_error_count=(job.invalid_rows or 0) + (job.warning_rows or 0),
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        created_by=job.created_by or "ระบบอัตโนมัติ",
        source_set_hash=job.source_set_hash,
        error_summary=job.error_summary,
    )


def _source_file_to_response(file: SourceFile) -> SourceFileResponse:
    return SourceFileResponse(
        file_id=file.id,
        file_name=file.file_name,
        file_path=file.file_path,
        file_type=file.file_type,
        sha256=file.sha256,
        size_bytes=file.size_bytes or 0,
        modified_at=file.source_modified_at,
        parse_status=file.parse_status,
        row_count=file.row_count,
        warning_count=file.warning_count,
        error_message=file.error_message,
        parse_error_summary=file.error_message,
        discovered_at=file.created_at,
    )


def _get_main_import_or_404(db: Session, import_id: UUID) -> ImportJob:
    job = db.get(ImportJob, import_id)
    if job is None or job.source_type != "main_history":
        raise HTTPException(status_code=404, detail="ไม่พบประวัติการนำเข้าข้อมูลการคัดกรองนี้")
    return job


def _list_job_source_files(db: Session, import_id: UUID) -> list[SourceFile]:
    return list(
        db.scalars(
            select(SourceFile)
            .where(SourceFile.import_job_id == import_id)
            .order_by(SourceFile.file_name, SourceFile.id)
        ).all()
    )


def _safe_existing_source_path(path_value: str | None) -> Path | None:
    if not path_value:
        return None
    candidate = Path(path_value).resolve()
    allowed_root = settings.source_data_dir.resolve()
    try:
        candidate.relative_to(allowed_root)
    except ValueError:
        return None
    if not candidate.is_file():
        return None
    return candidate


def _csv_response(rows: list[dict[str, object]], filename: str) -> StreamingResponse:
    output = io.StringIO()
    fieldnames = list(rows[0].keys()) if rows else ["message"]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows or [{"message": "no rows"}])
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/imports", response_model=ImportJobListResponse)
def list_imports(
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> ImportJobListResponse:
    logger.info("api.screening_database.list_imports limit=%s offset=%s", limit, offset)
    try:
        base_filter = ImportJob.source_type == "main_history"
        total = db.scalar(select(func.count()).select_from(ImportJob).where(base_filter)) or 0
        jobs = db.scalars(
            select(ImportJob)
            .where(base_filter)
            .order_by(desc(ImportJob.created_at), desc(ImportJob.id))
            .limit(limit)
            .offset(offset)
        ).all()
        imports = [_job_to_summary(job) for job in jobs]
        logger.info("api.screening_database.list_imports.success count=%s total=%s", len(imports), total)
        return ImportJobListResponse(imports=imports, total=total)
    except Exception as exc:
        logger.exception("api.screening_database.list_imports.failed")
        raise HTTPException(status_code=500, detail=f"ไม่สามารถโหลดประวัติการนำเข้าได้: {exc}") from exc


@router.get("/imports/{import_id}", response_model=ImportJobDetailResponse)
def get_import_detail(import_id: UUID, db: Session = Depends(get_db)) -> ImportJobDetailResponse:
    job = _get_main_import_or_404(db, import_id)
    files = [_source_file_to_response(item) for item in _list_job_source_files(db, job.id)]
    summary = _job_to_summary(job)
    return ImportJobDetailResponse(
        **summary.model_dump(),
        source_type=job.source_type,
        source_file_hash=job.source_file_hash,
        source_file_path=job.source_file_path,
        source_file_modified_at=job.source_file_modified_at,
        parsed_rows=job.parsed_rows,
        valid_rows=job.valid_rows,
        invalid_rows=job.invalid_rows,
        warning_rows=job.warning_rows,
        merged_rows=job.merged_rows,
        skipped_rows=job.skipped_rows,
        duplicate_identifier_count=job.duplicate_identifier_count,
        source_files=files,
    )


@router.get("/imports/{import_id}/download")
def download_import_source(import_id: UUID, db: Session = Depends(get_db)):
    job = _get_main_import_or_404(db, import_id)
    files = _list_job_source_files(db, job.id)
    if len(files) != 1:
        raise HTTPException(
            status_code=409,
            detail="import นี้มีหลายไฟล์ต้นทาง ให้ใช้รายงานสรุปหรือดูรายละเอียด import แทน",
        )
    source_path = _safe_existing_source_path(files[0].file_path)
    if source_path is None:
        raise HTTPException(status_code=404, detail="ไม่พบไฟล์ต้นทางในโฟลเดอร์ data หรือ path ไม่ปลอดภัย")
    return FileResponse(path=source_path, filename=files[0].file_name, media_type="application/octet-stream")


@router.get("/imports/{import_id}/report")
def download_import_report(import_id: UUID, db: Session = Depends(get_db)):
    job = _get_main_import_or_404(db, import_id)
    files = _list_job_source_files(db, job.id)
    rows = [
        {
            "import_id": str(job.id),
            "status": job.status,
            "source_file": file.file_name,
            "file_type": file.file_type,
            "file_size": file.size_bytes or 0,
            "sha256": file.sha256,
            "parse_status": file.parse_status,
            "row_count": file.row_count,
            "warning_count": file.warning_count,
            "error_message": file.error_message or "",
            "created_at": job.created_at.isoformat() if job.created_at else "",
            "started_at": job.started_at.isoformat() if job.started_at else "",
            "finished_at": job.finished_at.isoformat() if job.finished_at else "",
            "total_rows": job.total_rows,
            "success_rows": job.success_rows,
            "failed_rows": job.failed_rows,
            "invalid_rows": job.invalid_rows,
            "warning_rows": job.warning_rows,
            "source_set_hash": job.source_set_hash or "",
        }
        for file in files
    ]
    if not rows:
        rows = [
            {
                "import_id": str(job.id),
                "status": job.status,
                "source_file": job.source_file_name,
                "file_type": _detect_file_type(job.source_file_name),
                "file_size": job.source_file_size or 0,
                "sha256": job.source_file_hash,
                "parse_status": job.status,
                "row_count": job.total_rows,
                "warning_count": job.warning_rows,
                "error_message": job.error_summary or "",
                "created_at": job.created_at.isoformat() if job.created_at else "",
                "started_at": job.started_at.isoformat() if job.started_at else "",
                "finished_at": job.finished_at.isoformat() if job.finished_at else "",
                "total_rows": job.total_rows,
                "success_rows": job.success_rows,
                "failed_rows": job.failed_rows,
                "invalid_rows": job.invalid_rows,
                "warning_rows": job.warning_rows,
                "source_set_hash": job.source_set_hash or "",
            }
        ]
    return _csv_response(rows, f"screening-import-{str(job.id)[:8]}-summary.csv")


@router.post("/stage-upload", response_model=StageUploadResponse)
async def stage_upload_file(file: UploadFile = File(...)) -> StageUploadResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="ไม่พบชื่อไฟล์")

    filename = file.filename
    ext = Path(filename).suffix.lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=422,
            detail=f"ประเภทไฟล์ไม่รองรับ ('{ext}') — รองรับเฉพาะ: {', '.join(sorted(_ALLOWED_EXTENSIONS))}",
        )

    content = await file.read()
    file_size = len(content)
    if file_size == 0:
        raise HTTPException(status_code=422, detail="ไฟล์ว่างเปล่า — ไม่สามารถนำเข้าได้")
    if file_size > _MAX_FILE_SIZE_BYTES:
        mb = file_size / (1024 * 1024)
        raise HTTPException(status_code=422, detail=f"ไฟล์มีขนาดใหญ่เกิน 200 MB ({mb:.1f} MB)")

    file_type = _detect_file_type(filename)
    needs_review = ext == ".pdf"

    try:
        settings.source_data_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.exception("api.screening_database.stage_upload.mkdir_failed dir=%s", settings.source_data_dir)
        raise HTTPException(status_code=500, detail="ไม่สามารถสร้างโฟลเดอร์จัดเก็บไฟล์ได้") from exc

    dest_path = settings.source_data_dir / filename
    if dest_path.exists():
        stem = Path(filename).stem
        counter = 1
        while dest_path.exists():
            dest_path = settings.source_data_dir / f"{stem}_{counter}{ext}"
            counter += 1

    try:
        dest_path.write_bytes(content)
    except OSError as exc:
        logger.exception("api.screening_database.stage_upload.write_failed dest=%s", dest_path)
        raise HTTPException(status_code=500, detail="ไม่สามารถบันทึกไฟล์ได้") from exc

    if needs_review:
        message = (
            f"อัปโหลดไฟล์ PDF '{dest_path.name}' สำเร็จ "
            "แต่ระบบยังไม่รองรับการ parse PDF อัตโนมัติ ต้องตรวจสอบและแปลงข้อมูลก่อนนำเข้าจริง"
        )
        next_step = "ตรวจสอบและแปลงไฟล์ PDF ก่อน แล้วค่อย sync"
    else:
        message = (
            f"อัปโหลดไฟล์ '{dest_path.name}' สำเร็จ — ไฟล์ถูกจัดเตรียมไว้แล้ว "
            "กด 'ซิงก์ฐานข้อมูลการตรวจโรค' เพื่อนำเข้าข้อมูลจริง"
        )
        next_step = "กด 'ซิงก์ฐานข้อมูลการตรวจโรค' เพื่อนำเข้าข้อมูลจากไฟล์ที่อัปโหลด"

    return StageUploadResponse(
        status="staged_pdf_needs_review" if needs_review else "staged",
        file_name=dest_path.name,
        file_type=file_type,
        file_size=file_size,
        message=message,
        next_step=next_step,
        needs_review=needs_review,
    )
