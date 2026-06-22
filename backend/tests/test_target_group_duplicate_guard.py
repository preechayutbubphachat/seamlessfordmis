"""Duplicate target-group upload guard (D4.7.3 — idempotency after timeout retry).

Scenario: a large import made the client time out while the backend kept
working and committed the job. The user then retried with the exact same files
+ group name. The guard must NOT create a second target_group_jobs row — it
raises DuplicateUploadError pointing at the existing group.

Synthetic fixture only (tests/fixtures/desktop_local/) — no real patient data.
Run with: cd backend && pytest tests/test_target_group_duplicate_guard.py -v
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

_MULTISHEET_TG_FIXTURE = (
    Path(__file__).parent.parent.parent / "tests" / "fixtures" / "desktop_local" / "target_group_multisheet.xlsx"
)


class _MockUploadFile:
    """Minimal UploadFile stand-in: service uses only .filename and .file.read()."""

    def __init__(self, path: Path) -> None:
        self.filename = path.name
        self.file = path.open("rb")


def _build_schema_engine(db_path: Path):
    from app.db.base import Base
    from app.models import (  # noqa: F401 — side-effect: registers all mappers
        AuditLog,
        DiagnosisHistory,
        DiseaseMapping,
        DiseaseScreeningRecord,
        ImportJob,
        Patient,
        SourceFile,
        StagingHistoryRecord,
        TargetGroupHistoryRow,
        TargetGroupJob,
        TargetGroupJobFile,
        TargetGroupResult,
        TargetGroupResultSummary,
        TargetGroupRow,
        TargetGroupSheet,
    )

    engine = create_engine(f"sqlite:///{db_path}", future=True, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return engine


def test_duplicate_upload_guard(tmp_path, monkeypatch):
    if not _MULTISHEET_TG_FIXTURE.exists():
        pytest.skip(f"fixture missing: {_MULTISHEET_TG_FIXTURE}")

    from app.config import settings
    from app.models.target_group_job import TargetGroupJob
    from app.services.target_group_import_service import (
        DuplicateUploadError,
        TargetGroupImportService,
    )

    monkeypatch.setattr(settings, "upload_dir", tmp_path / "uploads")
    engine = _build_schema_engine(tmp_path / "dup.db")

    # First upload — succeeds, creates exactly one job.
    with Session(engine) as db:
        first = TargetGroupImportService.upload_files(
            db=db,
            group_name="dup_guard_test",
            upload_files=[_MockUploadFile(_MULTISHEET_TG_FIXTURE)],
            actor="pytest",
        )
        db.commit()
    assert first.group_id is not None

    # Retry — same files + same group name → guarded, no duplicate row.
    with Session(engine) as db:
        with pytest.raises(DuplicateUploadError) as exc_info:
            TargetGroupImportService.upload_files(
                db=db,
                group_name="dup_guard_test",
                upload_files=[_MockUploadFile(_MULTISHEET_TG_FIXTURE)],
                actor="pytest",
            )
        db.rollback()
    assert exc_info.value.group_id == first.group_id

    with Session(engine) as db:
        job_count = len(db.scalars(select(TargetGroupJob)).all())
    assert job_count == 1, "duplicate retry must not create a second target_group_jobs row"

    engine.dispose()


def test_different_group_name_same_files_is_allowed(tmp_path, monkeypatch):
    """Re-using the same roster under a *different* group name is NOT a duplicate."""
    if not _MULTISHEET_TG_FIXTURE.exists():
        pytest.skip(f"fixture missing: {_MULTISHEET_TG_FIXTURE}")

    from app.config import settings
    from app.models.target_group_job import TargetGroupJob
    from app.services.target_group_import_service import TargetGroupImportService

    monkeypatch.setattr(settings, "upload_dir", tmp_path / "uploads")
    engine = _build_schema_engine(tmp_path / "dup2.db")

    with Session(engine) as db:
        TargetGroupImportService.upload_files(
            db=db, group_name="quarter_1", upload_files=[_MockUploadFile(_MULTISHEET_TG_FIXTURE)], actor="pytest"
        )
        db.commit()
    with Session(engine) as db:
        TargetGroupImportService.upload_files(
            db=db, group_name="quarter_2", upload_files=[_MockUploadFile(_MULTISHEET_TG_FIXTURE)], actor="pytest"
        )
        db.commit()

    with Session(engine) as db:
        job_count = len(db.scalars(select(TargetGroupJob)).all())
    assert job_count == 2, "different group names must create separate jobs"

    engine.dispose()
