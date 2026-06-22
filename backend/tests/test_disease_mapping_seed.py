"""disease_mapping auto-seed (D4.7.4 — fix empty disease/service options on desktop).

Root cause fixed: desktop init created tables but never seeded the disease/service
catalog (disease_mapping), so /api/target-groups/disease-options returned [] and
the "สร้างผลลัพธ์" page had no options. seed_disease_mapping_if_empty() seeds the
real catalog (seed/disease_mapping_seed.json, fallback rows if absent) only when
the table is empty — idempotent, never wipes.

Synthetic only — no patient data. Run: cd backend && pytest tests/test_disease_mapping_seed.py -v
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker


def _build_schema_engine(db_path):
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


def test_seed_if_empty_populates_options_then_is_idempotent(tmp_path, monkeypatch):
    from app.models.disease_mapping import DiseaseMapping
    import app.seeds.disease_mapping_seed as seed_mod
    from app.services.target_group_import_service import TargetGroupImportService

    engine = _build_schema_engine(tmp_path / "dm.db")
    monkeypatch.setattr(seed_mod, "SessionLocal", sessionmaker(bind=engine, future=True))

    # Fresh DB → no catalog → options empty (this is the reported blocker state).
    with Session(engine) as db:
        assert TargetGroupImportService.disease_options(db) == []

    inserted = seed_mod.seed_disease_mapping_if_empty()
    assert inserted > 0, "seed must insert the real catalog into an empty table"

    with Session(engine) as db:
        options = TargetGroupImportService.disease_options(db)
    assert len(options) > 0, "options must be available after seeding"
    # Options are real catalog entries with keys/labels (not faked/blank).
    assert all(o.key and o.label for o in options)

    # Idempotent: second call must NOT duplicate or wipe.
    again = seed_mod.seed_disease_mapping_if_empty()
    assert again == 0
    with Session(engine) as db:
        total = db.scalar(select(func.count()).select_from(DiseaseMapping))
    assert total == inserted


def test_seed_if_empty_preserves_existing_rows(tmp_path, monkeypatch):
    """If the table already has data, seeding must be a no-op (no wipe)."""
    from app.models.disease_mapping import DiseaseMapping
    import app.seeds.disease_mapping_seed as seed_mod

    engine = _build_schema_engine(tmp_path / "dm2.db")
    TestSession = sessionmaker(bind=engine, future=True)
    monkeypatch.setattr(seed_mod, "SessionLocal", TestSession)

    with TestSession() as db:
        db.add(
            DiseaseMapping(
                raw_code=None,
                raw_name="custom",
                normalized_key="custom_key",
                normalized_label="custom label",
                icd10_code=None,
                is_active=True,
            )
        )
        db.commit()

    assert seed_mod.seed_disease_mapping_if_empty() == 0
    with TestSession() as db:
        rows = db.scalars(select(DiseaseMapping)).all()
    assert len(rows) == 1 and rows[0].normalized_key == "custom_key"
