#!/usr/bin/env python3
"""Phase F data population CLI.

Populates the linked-model scaffold tables created in migration 0013 and
made idempotent in migration 0014:

    person_master            — one row per deduplicated real-world person
    person_identifiers       — all known identifiers per person
    target_group_membership  — links target_group_rows → person_master
    disease_screening_events — links disease_screening_records → person_master

Usage
-----
Run all four steps (recommended):
    python scripts/phase_f_populate.py

Run a single step:
    python scripts/phase_f_populate.py --step person_master
    python scripts/phase_f_populate.py --step person_identifiers
    python scripts/phase_f_populate.py --step target_group_membership
    python scripts/phase_f_populate.py --step disease_screening_events

Dry-run (print counts without committing):
    python scripts/phase_f_populate.py --dry-run

Prerequisites
-------------
1.  Backend virtualenv active and DATABASE_URL set (or .env loaded).
2.  `alembic upgrade head` must be run first — migration 0014 adds the
    unique indexes required by this script.
3.  Result generation must have been run at least once so that
    canonical_person_key values are present on target_group_results.

The script is safe to run multiple times (idempotent).
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup — allow running from project root without installing the package.
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Load .env if python-dotenv is available (harmless if it isn't).
try:
    from dotenv import load_dotenv
    load_dotenv(BACKEND_DIR / ".env")
except ImportError:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("phase_f_populate")

VALID_STEPS = {
    "person_master",
    "person_identifiers",
    "target_group_membership",
    "disease_screening_events",
    "all",
}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Phase F: populate linked-model tables from normalised staging data.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--step",
        choices=sorted(VALID_STEPS),
        default="all",
        help="Which step to run (default: all)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print row counts but roll back — do not commit any changes.",
    )
    return parser.parse_args()


def _get_db_session():
    """Import and return a SQLAlchemy Session bound to DATABASE_URL."""
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        logger.error(
            "DATABASE_URL environment variable is not set.  "
            "Export it or add it to backend/.env before running this script."
        )
        sys.exit(1)

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(database_url)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def _check_migration_applied(db) -> bool:
    """Verify that migration 0014 has been applied (unique indexes exist)."""
    from sqlalchemy import text
    result = db.execute(
        text("SELECT 1 FROM pg_indexes WHERE indexname = 'uq_dse_source_record_id'")
    ).fetchone()
    return result is not None


def main() -> None:
    args = _parse_args()

    logger.info("Phase F population script starting  (step=%s, dry_run=%s)", args.step, args.dry_run)

    db = _get_db_session()

    # Guard: migration 0014 must be applied first.
    if not _check_migration_applied(db):
        logger.error(
            "Migration 0014 (phase_f_unique_constraints) has NOT been applied.\n"
            "Run:  alembic upgrade head\n"
            "then re-run this script."
        )
        db.close()
        sys.exit(1)

    from app.services.phase_f_population_service import PhaseFPopulationService

    start = time.monotonic()

    try:
        if args.step == "all":
            if args.dry_run:
                result = _dry_run_all(db, PhaseFPopulationService)
            else:
                result = PhaseFPopulationService.populate_all(db)
        elif args.step in _STEP_FN_MAP:
            if args.dry_run:
                result = _dry_run_step(db, PhaseFPopulationService, args.step)
            else:
                populate_fn = {
                    "person_master":            PhaseFPopulationService.populate_person_master,
                    "person_identifiers":       PhaseFPopulationService.populate_person_identifiers,
                    "target_group_membership":  PhaseFPopulationService.populate_target_group_membership,
                    "disease_screening_events": PhaseFPopulationService.populate_disease_screening_events,
                }[args.step]
                result = populate_fn(db)
        else:
            logger.error("Unknown step '%s'. Valid values: %s", args.step, sorted(VALID_STEPS))
            sys.exit(1)

        elapsed = time.monotonic() - start
        logger.info("Completed in %.1f s", elapsed)
        logger.info("=" * 60)
        for line in result.summary_lines():
            logger.info("  %s", line)
        logger.info("=" * 60)

        if result.errors:
            logger.warning("%d error(s) encountered — check logs above", len(result.errors))
            sys.exit(2)

        if args.dry_run:
            logger.info("DRY RUN — no changes committed.")

    except Exception:
        logger.exception("Unexpected error during Phase F population")
        db.rollback()
        db.close()
        sys.exit(1)
    finally:
        db.close()


_STEP_FN_MAP = {
    "person_master":            "_step_person_master",
    "person_identifiers":       "_step_person_identifiers",
    "target_group_membership":  "_step_target_group_membership",
    "disease_screening_events": "_step_disease_screening_events",
}


def _dry_run_all(db, svc):
    """Run all steps inside a savepoint then roll back — no data committed."""
    from app.services.phase_f_population_service import PhaseFPopulationResult
    result = PhaseFPopulationResult()
    sp = db.begin_nested()
    try:
        svc._step_person_master(db, result)
        db.flush()
        svc._step_person_identifiers(db, result)
        db.flush()
        svc._step_target_group_membership(db, result)
        db.flush()
        svc._step_disease_screening_events(db, result)
        db.flush()
    finally:
        sp.rollback()
    return result


def _dry_run_step(db, svc, step_name: str):
    """Run a single internal step inside a savepoint then roll back."""
    from app.services.phase_f_population_service import PhaseFPopulationResult
    result = PhaseFPopulationResult()
    internal_fn = getattr(svc, _STEP_FN_MAP[step_name])
    sp = db.begin_nested()
    try:
        internal_fn(db, result)
        db.flush()
    finally:
        sp.rollback()
    return result


if __name__ == "__main__":
    main()
