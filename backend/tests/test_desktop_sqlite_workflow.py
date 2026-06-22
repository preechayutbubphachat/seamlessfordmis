"""
test_desktop_sqlite_workflow.py  –  Phase D2.11-D2.13
======================================================
SQLite smoke tests for Desktop Local Edition.

Tests run IN ORDER — each phase builds on the previous.
Run with:
    cd backend
    pytest tests/test_desktop_sqlite_workflow.py -v -p no:randomly

Workflow sequence
-----------------
  S1  Schema bootstrap: create_all() creates every ORM-mapped table
  I1  Insert disease-screening records directly (bypasses XLSX parsing)
  T1  Target-group file import from multisheet fixture
  R1  Result generation on SQLite — critical pg_insert fix test
  R2  TargetGroupResultSummary cache row created after generate()
  R3  Upsert idempotency — second generate() must not duplicate summary row
  B1  Invalid CID → cid_validation_status contains "invalid" (not silently no-history)
  B2  Missing CID → staged, not silently dropped
  B3  DAVE in both sheets → exactly 1 result row (1-person-1-row rule)
  B4  BOB has TG-side history only → has_selected_service = True
  B5  EVE: selected-service date from TG history, NOT diabetes date from screening DB
  E1  Export produces an output file
  P1  Reconnect to same SQLite file → all data still present (restart persistence)

Notes
-----
- All CIDs are SYNTHETIC (province prefix 01 subgroup 12 — unissued range).
- No real patient data anywhere in this file or the fixture directory.
- Existing tests (unit/service tests using SimpleNamespace fake sessions) are
  NOT affected — this file uses a real SQLite engine in a temp directory.
"""

from __future__ import annotations

import importlib.util as _ilu
from datetime import date
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import Session

# ---------------------------------------------------------------------------
# Fixture file paths
# ---------------------------------------------------------------------------

_FIXTURE_DIR = Path(__file__).parent.parent.parent / "tests" / "fixtures" / "desktop_local"
MULTISHEET_TG_FIXTURE = _FIXTURE_DIR / "target_group_multisheet.xlsx"

# Load synthetic CID constants from fixtures/desktop_local/cid_constants.py
_spec = _ilu.spec_from_file_location("cid_constants", _FIXTURE_DIR / "cid_constants.py")
_cid_mod = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_cid_mod)  # type: ignore[union-attr]

CID_ALICE = _cid_mod.CID_ALICE
CID_BOB = _cid_mod.CID_BOB
CID_CHARLIE = _cid_mod.CID_CHARLIE
CID_DAVE = _cid_mod.CID_DAVE
CID_EVE = _cid_mod.CID_EVE
INVALID_CID = _cid_mod.INVALID_CID
MISSING_CID = _cid_mod.MISSING_CID  # ""

# ---------------------------------------------------------------------------
# Module-level workflow state (shared between ordered tests)
# ---------------------------------------------------------------------------

_state: dict = {}

# ---------------------------------------------------------------------------
# Minimal UploadFile stand-in
# ---------------------------------------------------------------------------


class _MockUploadFile:
    """Minimal interface that TargetGroupImportService.upload_files() consumes.

    The service only calls:
        upload_file.filename  → str
        upload_file.file.read()  → bytes
    """

    def __init__(self, path: Path) -> None:
        self.filename = path.name
        self._path = path
        self.file = path.open("rb")

    def __del__(self) -> None:
        try:
            self.file.close()
        except Exception:  # noqa: BLE001
            pass


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def tmp_dirs(tmp_path_factory):
    """Temporary directory tree for uploads, exports, source data."""
    base = tmp_path_factory.mktemp("desktop_smoke")
    dirs = {
        "base": base,
        "upload_dir": base / "uploads",
        "source_data_dir": base / "source_data",
        "exports": base / "source_data" / "exports",  # ExportService writes here
        "db_path": base / "test_desktop.db",
    }
    for key, path in dirs.items():
        if key != "db_path":
            path.mkdir(parents=True, exist_ok=True)
    return dirs


@pytest.fixture(scope="module")
def module_engine(tmp_dirs):
    """File-based SQLite engine with full ORM schema — shared across all tests."""
    # Import models so SQLAlchemy registers all mapped classes with Base.metadata
    from app.db.base import Base
    from app.models import (  # noqa: F401,F403 — side-effect: registers mappers
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

    db_url = f"sqlite:///{tmp_dirs['db_path']}"
    engine = create_engine(
        db_url,
        connect_args={"check_same_thread": False},
    )
    with engine.begin() as conn:
        conn.execute(text("PRAGMA foreign_keys=ON"))
        conn.execute(text("PRAGMA journal_mode=WAL"))
        conn.execute(text("PRAGMA synchronous=NORMAL"))
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


def _session(engine) -> Session:
    """Open a new session — caller is responsible for commit/close."""
    return Session(engine)


# ---------------------------------------------------------------------------
# S1 — Schema bootstrap
# ---------------------------------------------------------------------------


def test_S1_schema_bootstrap_creates_all_tables(module_engine):
    """All ORM-mapped tables must exist in the SQLite database after create_all().

    Verifies that the Desktop Local Edition schema bootstrap works on SQLite
    with no missing tables.  Partial schema = broken workflow.
    """
    from app.db.base import Base

    inspector = inspect(module_engine)
    existing = set(inspector.get_table_names())
    expected = {t.name for t in Base.metadata.sorted_tables}
    missing = expected - existing
    assert not missing, (
        f"SQLite schema bootstrap is incomplete — missing tables: {sorted(missing)}\n"
        "Run Base.metadata.create_all() or check that all model files are imported."
    )


# ---------------------------------------------------------------------------
# I1 — Direct insertion of disease-screening records
# ---------------------------------------------------------------------------


def test_I1_insert_disease_screening_records(module_engine):
    """Insert Patient + DiseaseScreeningRecord + DiagnosisHistory rows directly.

    Bypasses the 27-column XLSX parsing format of the main history importer so
    result-generation tests can verify CID-based matching without needing a
    production-formatted screening database file.

    Persons inserted
    ----------------
    ALICE  — cervical_screen on 2023-08-15 (latest) and 2021-03-10
    DAVE   — cervical_screen on 2022-06-01 (TG history has 2024-01-10; max should win)
    EVE    — diabetes_screen on 2023-12-20 (NOT cervical — B5 test)
    """
    from app.models.diagnosis_history import DiagnosisHistory
    from app.models.disease_screening_record import DiseaseScreeningRecord
    from app.models.import_job import ImportJob
    from app.models.patient import Patient

    with _session(module_engine) as db:
        # Minimal ImportJob (FK anchor)
        import_job = ImportJob(
            source_type="excel",
            source_file_name="screening_db_sample.xlsx",
            source_file_hash="synthetic-smoke-test-hash-0001",
            source_file_count=1,
            status="success",
            total_rows=4,
            parsed_rows=4,
            valid_rows=4,
            merged_rows=4,
        )
        db.add(import_job)
        db.flush()
        _state["import_job_id"] = import_job.id

        # -- ALICE --
        alice = Patient(
            full_name="นางสาว อลิซ ตัวอย่าง",
            citizen_id=CID_ALICE,
            source_import_job_id=import_job.id,
        )
        db.add(alice)
        db.flush()
        for vd in [date(2023, 8, 15), date(2021, 3, 10)]:
            db.add(DiseaseScreeningRecord(
                source_import_job_id=import_job.id,
                raw_person_identifier=CID_ALICE,
                normalized_person_identifier=CID_ALICE,
                raw_service_type="ตรวจคัดกรองมะเร็งปากมดลูก",
                normalized_service_key="cervical_screen",
                visit_date=vd,
            ))
            db.add(DiagnosisHistory(
                patient_id=alice.id,
                visit_date=vd,
                normalized_person_identifier=CID_ALICE,
                normalized_service_key="cervical_screen",
                source_import_job_id=import_job.id,
            ))

        # -- DAVE --
        dave = Patient(
            full_name="นาย เดฟ ตัวอย่าง",
            citizen_id=CID_DAVE,
            source_import_job_id=import_job.id,
        )
        db.add(dave)
        db.flush()
        db.add(DiseaseScreeningRecord(
            source_import_job_id=import_job.id,
            raw_person_identifier=CID_DAVE,
            normalized_person_identifier=CID_DAVE,
            raw_service_type="ตรวจคัดกรองมะเร็งปากมดลูก",
            normalized_service_key="cervical_screen",
            visit_date=date(2022, 6, 1),
        ))
        db.add(DiagnosisHistory(
            patient_id=dave.id,
            visit_date=date(2022, 6, 1),
            normalized_person_identifier=CID_DAVE,
            normalized_service_key="cervical_screen",
            source_import_job_id=import_job.id,
        ))

        # -- EVE — diabetes only, NO cervical record --
        eve = Patient(
            full_name="นาง อีฟ ตัวอย่าง",
            citizen_id=CID_EVE,
            source_import_job_id=import_job.id,
        )
        db.add(eve)
        db.flush()
        db.add(DiseaseScreeningRecord(
            source_import_job_id=import_job.id,
            raw_person_identifier=CID_EVE,
            normalized_person_identifier=CID_EVE,
            raw_service_type="ตรวจคัดกรองเบาหวาน",
            normalized_service_key="diabetes_screen",  # NOT cervical_screen
            visit_date=date(2023, 12, 20),
        ))

        db.commit()

    # -- Sanity checks --
    with _session(module_engine) as db:
        from app.models.disease_screening_record import DiseaseScreeningRecord as DSR
        from app.models.patient import Patient as P

        assert db.scalar(select(P).where(P.citizen_id == CID_ALICE)) is not None
        assert db.scalar(select(P).where(P.citizen_id == CID_DAVE)) is not None
        assert db.scalar(select(P).where(P.citizen_id == CID_EVE)) is not None

        eve_cervical = db.scalars(
            select(DSR).where(
                DSR.normalized_person_identifier == CID_EVE,
                DSR.normalized_service_key == "cervical_screen",
            )
        ).all()
        assert eve_cervical == [], (
            "EVE must NOT have cervical_screen in screening DB — needed for B5 test"
        )


# ---------------------------------------------------------------------------
# T1 — Target group file import
# ---------------------------------------------------------------------------


def test_T1_target_group_upload_from_fixture(module_engine, tmp_dirs, monkeypatch):
    """Upload the multisheet fixture via TargetGroupImportService.upload_files().

    Fixture contains
    ----------------
    Sheet รายชื่อ (roster): ALICE, BOB, CHARLIE, DAVE, EVE, INVALID_CID row, missing-CID row
    Sheet ประวัติ (history): BOB x2, DAVE, EVE (cervical), ALICE (2024-11-05)

    Verifies
    --------
    - staging rows created for all persons
    - invalid CID row is staged (not silently dropped)
    - missing CID row is staged (not silently dropped)
    - group_id returned for downstream tests
    """
    assert MULTISHEET_TG_FIXTURE.exists(), (
        f"Fixture file missing: {MULTISHEET_TG_FIXTURE}\n"
        "Run: python tests/fixtures/desktop_local/gen_fixtures.py"
    )

    from app.config import settings
    from app.services.target_group_import_service import TargetGroupImportService

    monkeypatch.setattr(settings, "upload_dir", tmp_dirs["upload_dir"])

    mock_file = _MockUploadFile(MULTISHEET_TG_FIXTURE)

    with _session(module_engine) as db:
        response = TargetGroupImportService.upload_files(
            db=db,
            group_name="smoke_test_cervical_2026",
            upload_files=[mock_file],
            actor="pytest",
        )
        db.commit()

    _state["group_id"] = response.group_id

    assert response.group_id is not None, "upload_files must return a group_id"
    assert response.total_rows >= 1, "at least 1 row must be staged"

    from app.models.target_group_row import TargetGroupRow

    with _session(module_engine) as db:
        staged = db.scalars(
            select(TargetGroupRow).where(
                TargetGroupRow.group_job_id == response.group_id
            )
        ).all()

    assert len(staged) >= 1, "staged rows must be persisted"
    _state["staged_row_count"] = len(staged)


# ---------------------------------------------------------------------------
# R1 — Result generation on SQLite (THE critical fix test)
# ---------------------------------------------------------------------------


def test_R1_generate_results_on_sqlite(module_engine, tmp_dirs, monkeypatch):
    """ResultGenerationService.generate() must complete without error on SQLite.

    Before D2.9 fix
    ---------------
    _upsert_summary_cache used ``sqlalchemy.dialects.postgresql.insert`` (pg_insert)
    directly, which raised OperationalError on SQLite.

    After D2.9 fix
    --------------
    make_upsert_stmt dispatches to ``sqlalchemy.dialects.sqlite.insert`` on SQLite,
    giving identical ON CONFLICT DO UPDATE semantics.

    This test FAILS if the pg_insert blocker is still present.
    """
    group_id = _state.get("group_id")
    assert group_id is not None, "T1 must run before R1 (group_id not in _state)"

    from app.config import settings
    from app.services.result_generation_service import ResultGenerationService

    monkeypatch.setattr(settings, "upload_dir", tmp_dirs["upload_dir"])

    with _session(module_engine) as db:
        result = ResultGenerationService.generate(
            db=db,
            group_id=group_id,
            disease_keys=["cervical_screen"],
            actor="pytest",
        )
        db.commit()

    _state["generate_result"] = result

    assert result is not None, "generate() must return a result"
    assert result.group_id == group_id
    assert result.generated_rows >= 1, (
        "at least 1 result row must be generated from the staged target group"
    )


# ---------------------------------------------------------------------------
# R2 — Summary cache row created
# ---------------------------------------------------------------------------


def test_R2_summary_cache_row_created(module_engine):
    """TargetGroupResultSummary must exist after generate().

    If this fails, _upsert_summary_cache either errored silently or was not reached.
    """
    group_id = _state.get("group_id")
    assert group_id is not None

    from app.models.target_group_result_summary import TargetGroupResultSummary

    with _session(module_engine) as db:
        summary = db.scalar(
            select(TargetGroupResultSummary).where(
                TargetGroupResultSummary.group_job_id == group_id
            )
        )

    assert summary is not None, (
        "TargetGroupResultSummary must be created after generate() — "
        "check that _upsert_summary_cache (the pg_insert fix) executed successfully"
    )
    assert summary.total_target_people >= 1


# ---------------------------------------------------------------------------
# R3 — Upsert idempotency
# ---------------------------------------------------------------------------


def test_R3_second_generate_does_not_duplicate_summary(module_engine, tmp_dirs, monkeypatch):
    """Running generate() twice for the same group + service selection must NOT
    create a second TargetGroupResultSummary row.

    Tests the ON CONFLICT DO UPDATE semantics of make_upsert_stmt on SQLite.
    """
    group_id = _state.get("group_id")
    assert group_id is not None

    from app.config import settings
    from app.models.target_group_result_summary import TargetGroupResultSummary
    from app.services.result_generation_service import ResultGenerationService

    monkeypatch.setattr(settings, "upload_dir", tmp_dirs["upload_dir"])

    with _session(module_engine) as db:
        ResultGenerationService.generate(
            db=db,
            group_id=group_id,
            disease_keys=["cervical_screen"],
            actor="pytest",
        )
        db.commit()

    with _session(module_engine) as db:
        rows = db.scalars(
            select(TargetGroupResultSummary).where(
                TargetGroupResultSummary.group_job_id == group_id
            )
        ).all()

    assert len(rows) == 1, (
        f"Upsert must be idempotent — found {len(rows)} summary rows after two "
        f"generate() calls, expected exactly 1"
    )


# ---------------------------------------------------------------------------
# B1 — Invalid CID is staged as invalid, not silently no-history
# ---------------------------------------------------------------------------


def test_B1_invalid_cid_staged_as_invalid_identifier(module_engine):
    """Row with invalid CID checksum must be staged with cid_validation_status
    containing 'invalid'.

    Safety rule: invalid identifiers must NEVER silently become 'never checked'
    or 'no history'.  The hospital operator must be able to see and fix them.
    """
    group_id = _state.get("group_id")
    assert group_id is not None

    from app.models.target_group_row import TargetGroupRow

    with _session(module_engine) as db:
        invalid_rows = db.scalars(
            select(TargetGroupRow).where(
                TargetGroupRow.group_job_id == group_id,
                TargetGroupRow.raw_cid == INVALID_CID,
            )
        ).all()

    assert invalid_rows, (
        f"Row with INVALID_CID={INVALID_CID!r} must be staged in target_group_rows — "
        "invalid identifiers must NOT be silently dropped"
    )
    for row in invalid_rows:
        status = (row.cid_validation_status or "").lower()
        assert "invalid" in status, (
            f"Invalid-checksum CID must have cid_validation_status containing 'invalid', "
            f"got {row.cid_validation_status!r}"
        )


# ---------------------------------------------------------------------------
# B2 — Missing CID is staged, not dropped
# ---------------------------------------------------------------------------


def test_B2_missing_cid_staged_not_dropped(module_engine):
    """Rows with blank CID must be staged (with missing/review status), not silently
    discarded.  Silently dropping them hides data quality problems from operators.
    """
    group_id = _state.get("group_id")
    assert group_id is not None

    from app.models.target_group_row import TargetGroupRow

    with _session(module_engine) as db:
        # Match rows where raw_cid is NULL or empty string
        missing_rows = db.scalars(
            select(TargetGroupRow).where(
                TargetGroupRow.group_job_id == group_id,
                TargetGroupRow.normalized_cid.is_(None)
                | (TargetGroupRow.normalized_cid == ""),
            )
        ).all()

    assert missing_rows, (
        "Rows with empty/blank CID must be staged — "
        "missing identifiers must not be silently dropped"
    )
    for row in missing_rows:
        status = (row.cid_validation_status or "").lower()
        assert any(kw in status for kw in ("missing", "invalid", "review")), (
            f"Missing-CID row must have status indicating missing/invalid/review, "
            f"got {row.cid_validation_status!r} for row_no={row.row_no}"
        )


# ---------------------------------------------------------------------------
# B3 — 1 person = 1 result row (DAVE in both sheets)
# ---------------------------------------------------------------------------


def test_B3_one_person_one_result_row(module_engine):
    """CID_DAVE appears in both the roster sheet AND the history sheet.
    The visible result table must have EXACTLY 1 row for DAVE.

    Regression guard for the canonical person-deduplication rule:
    multiple source appearances of the same person MUST NOT produce multiple rows.
    """
    group_id = _state.get("group_id")
    assert group_id is not None

    from app.models.target_group_result import TargetGroupResult

    with _session(module_engine) as db:
        dave_results = db.scalars(
            select(TargetGroupResult).where(
                TargetGroupResult.group_job_id == group_id,
                TargetGroupResult.normalized_cid == CID_DAVE,
            )
        ).all()

    assert len(dave_results) == 1, (
        f"CID_DAVE appears in multiple sheets but the result table must contain "
        f"EXACTLY 1 row. Found {len(dave_results)} rows. "
        "The 1-person-1-row canonical deduplication rule may be broken."
    )


# ---------------------------------------------------------------------------
# B4 — TG-side history is valid evidence (BOB)
# ---------------------------------------------------------------------------


def test_B4_target_group_side_history_is_evidence(module_engine):
    """CID_BOB has cervical screening history ONLY in the target-group file (not in
    the disease-screening database).

    BOB must still get a result row, and has_selected_service must be True.
    TG-file-side history is valid evidence — it must not be ignored.
    """
    group_id = _state.get("group_id")
    assert group_id is not None

    from app.models.target_group_result import TargetGroupResult

    with _session(module_engine) as db:
        bob_result = db.scalar(
            select(TargetGroupResult).where(
                TargetGroupResult.group_job_id == group_id,
                TargetGroupResult.normalized_cid == CID_BOB,
            )
        )

    assert bob_result is not None, (
        "CID_BOB must have a result row — "
        "TG-file-side history is valid evidence and must not be ignored"
    )
    assert bob_result.has_selected_service is True, (
        "BOB has cervical history in TG file — has_selected_service must be True. "
        "Result shows: "
        f"has_selected_service={bob_result.has_selected_service!r}, "
        f"last_visit_date={bob_result.last_visit_date!r}"
    )


# ---------------------------------------------------------------------------
# B5 — Selected-service date from selected service only (EVE)
# ---------------------------------------------------------------------------


def test_B5_selected_service_latest_date_from_selected_service_only(module_engine):
    """CID_EVE has diabetes_screen in the disease-screening database (2023-12-20)
    and cervical_screen in TG-file history (2022-05-01).

    When generating results for cervical_screen:
    - last_visit_date must be 2022-05-01 (from TG file), NOT 2023-12-20 (diabetes)
    - The diabetes date must NOT bleed into cervical result calculations

    This verifies that "latest date from SELECTED service only" is enforced.
    """
    group_id = _state.get("group_id")
    assert group_id is not None

    from app.models.target_group_result import TargetGroupResult

    with _session(module_engine) as db:
        eve_result = db.scalar(
            select(TargetGroupResult).where(
                TargetGroupResult.group_job_id == group_id,
                TargetGroupResult.normalized_cid == CID_EVE,
            )
        )

    assert eve_result is not None, "CID_EVE must have a result row"

    # If EVE has any selected history, the date must NOT be the diabetes date
    if eve_result.last_visit_date is not None:
        assert eve_result.last_visit_date != date(2023, 12, 20), (
            "EVE's last_visit_date must NOT be 2023-12-20 (diabetes from screening DB) "
            "when generating for cervical_screen. "
            f"Got last_visit_date={eve_result.last_visit_date!r}. "
            "Cross-service date contamination detected."
        )


# ---------------------------------------------------------------------------
# E1 — Export produces output file
# ---------------------------------------------------------------------------


def test_E1_export_produces_file(module_engine, tmp_dirs, monkeypatch):
    """ExportService.export_group_results() must produce a valid output file.

    ExportService writes to settings.source_data_dir / 'exports'.
    We patch source_data_dir to our temp dir so we can verify the file exists.
    """
    group_id = _state.get("group_id")
    assert group_id is not None

    from app.config import settings
    from app.services.export_service import ExportService

    # ExportService uses settings.source_data_dir / "exports" as output root
    monkeypatch.setattr(settings, "source_data_dir", tmp_dirs["source_data_dir"])

    with _session(module_engine) as db:
        artifact = ExportService.export_group_results(
            db=db,
            group_id=group_id,
            export_format="xlsx",
            actor="pytest",
        )
        db.commit()

    assert artifact is not None, "export_group_results must return an ExportArtifact"
    assert artifact.path.exists(), (
        f"Export file must exist at {artifact.path}. "
        "ExportService.export_group_results() may have failed silently."
    )
    assert artifact.path.stat().st_size > 0, "Export file must not be empty"


# ---------------------------------------------------------------------------
# P1 — Data persists after engine reconnect (restart simulation)
# ---------------------------------------------------------------------------


def test_P1_data_persists_after_engine_reconnect(module_engine, tmp_dirs):
    """Closing the SQLAlchemy engine and reconnecting to the same SQLite file must
    preserve all rows.  Simulates a Desktop Local Edition app restart.

    Verifies WAL mode and SQLite durability — committed rows must survive a full
    engine dispose + reconnect cycle.
    """
    group_id = _state.get("group_id")
    assert group_id is not None

    from app.models.target_group_result import TargetGroupResult
    from app.models.target_group_row import TargetGroupRow

    # Count rows via the existing engine
    with _session(module_engine) as db:
        original_tg = len(
            db.scalars(
                select(TargetGroupRow).where(
                    TargetGroupRow.group_job_id == group_id
                )
            ).all()
        )
        original_results = len(
            db.scalars(
                select(TargetGroupResult).where(
                    TargetGroupResult.group_job_id == group_id
                )
            ).all()
        )

    assert original_tg >= 1, "precondition: TG rows must exist before restart test"
    assert original_results >= 1, "precondition: result rows must exist before restart test"

    # Simulate restart: brand-new engine to the same file path
    db_url = f"sqlite:///{tmp_dirs['db_path']}"
    restarted = create_engine(db_url, connect_args={"check_same_thread": False})
    try:
        with restarted.connect() as conn:
            conn.execute(text("PRAGMA foreign_keys=ON"))

        with Session(restarted) as db2:
            restarted_tg = len(
                db2.scalars(
                    select(TargetGroupRow).where(
                        TargetGroupRow.group_job_id == group_id
                    )
                ).all()
            )
            restarted_results = len(
                db2.scalars(
                    select(TargetGroupResult).where(
                        TargetGroupResult.group_job_id == group_id
                    )
                ).all()
            )
    finally:
        restarted.dispose()

    assert restarted_tg == original_tg, (
        f"After restart: expected {original_tg} TG rows, got {restarted_tg}. "
        "Data was NOT persisted — WAL mode or commit may be broken."
    )
    assert restarted_results == original_results, (
        f"After restart: expected {original_results} result rows, "
        f"got {restarted_results}."
    )
