"""Result staleness guard via normalization_version (D4.7.6 — B1 stale results).

A cached result summary stamped with an older normalization/classification
version (or NULL, i.e. generated before the column existed) must be flagged
`requires_regeneration=True` so the UI can prompt the user to regenerate.
A summary stamped with the current version must NOT be flagged.

No classification logic is changed; this only adds a staleness signal.
Synthetic only — no patient data.
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import Session


def _build_schema_engine(db_path):
    from app.db.base import Base
    from app.models import (  # noqa: F401 — registers mappers
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


def _insert_summary(db, group_id, normalization_version):
    from app.models.target_group_result_summary import TargetGroupResultSummary

    db.add(
        TargetGroupResultSummary(
            group_job_id=group_id,
            selected_service_hash="hash",
            selected_service_keys=["hpv_screen"],
            total_target_people=1,
            valid_identifier_people=1,
            coverage_percent=0,
            generated_at=datetime.now(),
            normalization_version=normalization_version,
        )
    )
    db.commit()


def test_current_version_not_stale(tmp_path):
    from app.services.result_generation_service import (
        RESULT_NORMALIZATION_VERSION,
        ResultGenerationService,
    )

    engine = _build_schema_engine(tmp_path / "v.db")
    group_id = uuid4()
    with Session(engine) as db:
        _insert_summary(db, group_id, RESULT_NORMALIZATION_VERSION)
    with Session(engine) as db:
        summary = ResultGenerationService.get_result_summary(db, group_id)
    assert summary.normalization_version == RESULT_NORMALIZATION_VERSION
    assert summary.requires_regeneration is False
    engine.dispose()


def test_old_version_is_stale(tmp_path):
    from app.services.result_generation_service import ResultGenerationService

    engine = _build_schema_engine(tmp_path / "v_old.db")
    group_id = uuid4()
    with Session(engine) as db:
        _insert_summary(db, group_id, 1)  # older than current
    with Session(engine) as db:
        summary = ResultGenerationService.get_result_summary(db, group_id)
    assert summary.requires_regeneration is True
    engine.dispose()


def test_null_version_is_stale(tmp_path):
    """Rows generated before the column existed read as NULL → must be flagged."""
    from app.services.result_generation_service import ResultGenerationService

    engine = _build_schema_engine(tmp_path / "v_null.db")
    group_id = uuid4()
    with Session(engine) as db:
        _insert_summary(db, group_id, None)
    with Session(engine) as db:
        summary = ResultGenerationService.get_result_summary(db, group_id)
    assert summary.requires_regeneration is True
    engine.dispose()
