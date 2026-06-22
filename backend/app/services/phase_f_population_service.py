"""Phase F: Populate the linked-model scaffold tables.

Migration 0013 (phase_e_perf_indexes_linked_scaffold) created four empty
tables:  person_master, person_identifiers, disease_screening_events, and
target_group_membership.  This service fills them from the data already
normalised and stored in Phases B–E.

Entry points
------------
PhaseFPopulationService.populate_all(db)           — run all four phases
PhaseFPopulationService.populate_person_master(db) — step 1 only
PhaseFPopulationService.populate_person_identifiers(db) — step 2 only
PhaseFPopulationService.populate_target_group_membership(db) — step 3 only
PhaseFPopulationService.populate_disease_screening_events(db) — step 4 only

Each step is idempotent: re-running it is safe.  Rows that already exist
(matched on their unique constraint) are skipped via ON CONFLICT DO NOTHING
so partial runs can be resumed without producing duplicates.

Safety rules
------------
- Raw source values are never silently overwritten with inferred data.
- Rows with NULL canonical_person_key in target_group_results are skipped.
- person_master is only updated (display_name / primary_cid) when the new
  value is non-NULL and the existing column is NULL, never the other way.
- No fuzzy matching is performed here; all linkage comes from the
  canonical_person_key already computed and stored by result_generation_service.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.db.compat import raise_if_sqlite_unsupported as _raise_if_sqlite_unsupported

from app.models.disease_screening_record import DiseaseScreeningRecord
from app.models.target_group_result import TargetGroupResult
from app.models.target_group_row import TargetGroupRow

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class PhaseFPopulationResult:
    """Counts returned by each population step."""

    person_master_inserted: int = 0
    person_master_skipped: int = 0
    person_identifiers_inserted: int = 0
    person_identifiers_skipped: int = 0
    target_group_membership_inserted: int = 0
    target_group_membership_skipped: int = 0
    disease_screening_events_inserted: int = 0
    disease_screening_events_skipped: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def total_inserted(self) -> int:
        return (
            self.person_master_inserted
            + self.person_identifiers_inserted
            + self.target_group_membership_inserted
            + self.disease_screening_events_inserted
        )

    def summary_lines(self) -> list[str]:
        lines = [
            f"person_master:             {self.person_master_inserted} inserted, {self.person_master_skipped} skipped",
            f"person_identifiers:        {self.person_identifiers_inserted} inserted, {self.person_identifiers_skipped} skipped",
            f"target_group_membership:   {self.target_group_membership_inserted} inserted, {self.target_group_membership_skipped} skipped",
            f"disease_screening_events:  {self.disease_screening_events_inserted} inserted, {self.disease_screening_events_skipped} skipped",
        ]
        if self.errors:
            lines.append(f"ERRORS ({len(self.errors)}): " + "; ".join(self.errors[:5]))
        return lines


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_cid_from_key(canonical_person_key: str) -> str | None:
    """Return the CID embedded in a ``cid:<value>`` canonical key."""
    if canonical_person_key.startswith("cid:"):
        cid = canonical_person_key[4:]
        return cid if cid else None
    return None


def _extract_name_from_key(canonical_person_key: str) -> str | None:
    """Return the name embedded in a ``name_birth:<name>:<dob>`` key."""
    if canonical_person_key.startswith("name_birth:"):
        parts = canonical_person_key.split(":", 2)
        # format: name_birth:<name>:<dob>
        if len(parts) >= 3:
            return parts[1] or None
    return None


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

BATCH_SIZE = 500


class PhaseFPopulationService:
    """Populate the Phase F linked-model scaffold tables."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @classmethod
    def populate_all(cls, db: Session) -> PhaseFPopulationResult:
        """Run all four population steps in dependency order and commit once.

        .. warning::
            This method is **not yet ported to SQLite**.  It uses
            PostgreSQL-specific raw SQL (``ON CONFLICT DO NOTHING`` inside
            ``text()`` blocks).  Calling it on a SQLite session will raise
            ``NotImplementedError`` so the failure is explicit.
            Tracked as a blocker in docs/DESKTOP_SQLITE_D3_WORKFLOW_NOTES.md.
        """
        _raise_if_sqlite_unsupported(db, "PhaseFPopulationService.populate_all")
        result = PhaseFPopulationResult()
        logger.info("phase_f.populate_all: starting")

        cls._step_person_master(db, result)
        db.flush()

        cls._step_person_identifiers(db, result)
        db.flush()

        cls._step_target_group_membership(db, result)
        db.flush()

        cls._step_disease_screening_events(db, result)
        db.flush()

        db.commit()
        for line in result.summary_lines():
            logger.info("phase_f.populate_all: %s", line)
        return result

    @classmethod
    def populate_person_master(cls, db: Session) -> PhaseFPopulationResult:
        result = PhaseFPopulationResult()
        cls._step_person_master(db, result)
        db.commit()
        return result

    @classmethod
    def populate_person_identifiers(cls, db: Session) -> PhaseFPopulationResult:
        result = PhaseFPopulationResult()
        cls._step_person_identifiers(db, result)
        db.commit()
        return result

    @classmethod
    def populate_target_group_membership(cls, db: Session) -> PhaseFPopulationResult:
        result = PhaseFPopulationResult()
        cls._step_target_group_membership(db, result)
        db.commit()
        return result

    @classmethod
    def populate_disease_screening_events(cls, db: Session) -> PhaseFPopulationResult:
        result = PhaseFPopulationResult()
        cls._step_disease_screening_events(db, result)
        db.commit()
        return result

    # ------------------------------------------------------------------
    # Step 1: person_master
    # ------------------------------------------------------------------

    @classmethod
    def _step_person_master(cls, db: Session, result: PhaseFPopulationResult) -> None:
        """Upsert one person_master row per unique canonical_person_key.

        Source: target_group_results (canonical_person_key, normalized_cid,
        full_name, sex, last_visit_date) joined to target_group_rows for birth
        date.  We choose the best available display_name and primary_cid from
        all results sharing the same key.

        ON CONFLICT (canonical_person_key) DO NOTHING so existing rows are
        preserved.  A second pass fills NULL display_name / primary_cid on
        existing rows where we now have better data.
        """
        logger.info("phase_f.step1: collecting distinct canonical_person_keys from target_group_results")

        # Collect distinct keys with the richest available identity data.
        # We take the MAX of name / cid / sex so at least one non-NULL row wins.
        raw_keys: list[tuple] = db.execute(
            text("""
                SELECT
                    r.canonical_person_key,
                    MAX(r.full_name)        AS display_name,
                    MAX(r.normalized_cid)   AS primary_cid,
                    MAX(r.sex)              AS primary_sex
                FROM target_group_results r
                WHERE r.canonical_person_key IS NOT NULL
                GROUP BY r.canonical_person_key
            """)
        ).fetchall()

        if not raw_keys:
            logger.info("phase_f.step1: no rows with canonical_person_key found — nothing to do")
            return

        logger.info("phase_f.step1: %d distinct canonical_person_keys to upsert", len(raw_keys))

        # Check which keys already exist so we can report skips vs inserts.
        existing: set[str] = set(
            db.scalars(text("SELECT canonical_person_key FROM person_master")).all()
        )

        batch: list[dict] = []
        for row in raw_keys:
            key = row[0]
            if key in existing:
                result.person_master_skipped += 1
                continue

            primary_cid = row[2] or _extract_cid_from_key(key)
            display_name = row[1] or _extract_name_from_key(key)

            batch.append({
                "canonical_person_key": key,
                "display_name": display_name,
                "primary_cid": primary_cid,
                "primary_sex": row[3],
            })

            if len(batch) >= BATCH_SIZE:
                cls._insert_person_master_batch(db, batch, result)
                batch = []

        if batch:
            cls._insert_person_master_batch(db, batch, result)

        # Back-fill NULL display_name / primary_cid on already-existing rows
        # where we now have better data (only sets NULL→non-NULL, never overwrites).
        for row in raw_keys:
            key = row[0]
            if key not in existing:
                continue
            new_cid = row[2] or _extract_cid_from_key(key)
            new_name = row[1] or _extract_name_from_key(key)
            if new_cid or new_name:
                db.execute(
                    text("""
                        UPDATE person_master
                        SET
                            display_name = COALESCE(display_name, :name),
                            primary_cid  = COALESCE(primary_cid,  :cid),
                            updated_at   = now()
                        WHERE canonical_person_key = :key
                          AND (display_name IS NULL OR primary_cid IS NULL)
                    """),
                    {"key": key, "name": new_name, "cid": new_cid},
                )

    @staticmethod
    def _insert_person_master_batch(
        db: Session,
        batch: list[dict],
        result: PhaseFPopulationResult,
    ) -> None:
        db.execute(
            text("""
                INSERT INTO person_master
                    (canonical_person_key, display_name, primary_cid, primary_sex)
                VALUES
                    (:canonical_person_key, :display_name, :primary_cid, :primary_sex)
                ON CONFLICT (canonical_person_key) DO NOTHING
            """),
            batch,
        )
        result.person_master_inserted += len(batch)
        logger.debug("phase_f.step1: inserted batch of %d person_master rows", len(batch))

    # ------------------------------------------------------------------
    # Step 2: person_identifiers
    # ------------------------------------------------------------------

    @classmethod
    def _step_person_identifiers(cls, db: Session, result: PhaseFPopulationResult) -> None:
        """Insert person_identifiers rows for each person_master.

        Identifier types produced:
          - "citizen_id"      from canonical_person_key starting with "cid:"
          - "name_birthdate"  from canonical_person_key starting with "name_birth:"
          - "canonical_key"   full key value, always present

        ON CONFLICT (person_id, identifier_type, identifier_value) DO NOTHING
        for idempotency.  Because person_identifiers has no such unique
        constraint in the schema, we check existence before inserting.
        """
        logger.info("phase_f.step2: populating person_identifiers")

        # Fetch all person_master rows to build identifier rows from.
        persons: list[tuple] = db.execute(
            text("SELECT id, canonical_person_key, primary_cid FROM person_master")
        ).fetchall()

        # Fetch already-existing (person_id, identifier_value) pairs to skip.
        existing_pairs: set[tuple] = {
            (row[0], row[1])
            for row in db.execute(
                text("SELECT person_id, identifier_value FROM person_identifiers")
            ).fetchall()
        }

        to_insert: list[dict] = []

        for person_row in persons:
            person_id: UUID = person_row[0]
            key: str = person_row[1]
            primary_cid: str | None = person_row[2]

            def _queue(id_type: str, id_value: str, confidence: str) -> None:
                pair = (person_id, id_value)
                if pair in existing_pairs:
                    result.person_identifiers_skipped += 1
                    return
                to_insert.append({
                    "person_id": str(person_id),
                    "identifier_type": id_type,
                    "identifier_value": id_value,
                    "confidence": confidence,
                })
                existing_pairs.add(pair)  # prevent within-batch duplicates

            # Always store the full canonical key.
            _queue("canonical_key", key, "high")

            # Extract CID.
            cid = primary_cid or _extract_cid_from_key(key)
            if cid:
                _queue("citizen_id", cid, "high")

            # For name_birth keys, store the encoded value as a secondary identifier.
            if key.startswith("name_birth:"):
                _queue("name_birthdate", key[len("name_birth:"):], "medium")

            if len(to_insert) >= BATCH_SIZE:
                cls._insert_identifiers_batch(db, to_insert, result)
                to_insert = []

        if to_insert:
            cls._insert_identifiers_batch(db, to_insert, result)

    @staticmethod
    def _insert_identifiers_batch(
        db: Session,
        batch: list[dict],
        result: PhaseFPopulationResult,
    ) -> None:
        # Migration 0014 adds uq_person_identifiers_person_type_value unique index.
        db.execute(
            text("""
                INSERT INTO person_identifiers
                    (person_id, identifier_type, identifier_value, confidence)
                VALUES
                    (:person_id, :identifier_type, :identifier_value, :confidence)
                ON CONFLICT (person_id, identifier_type, identifier_value) DO NOTHING
            """),
            batch,
        )
        result.person_identifiers_inserted += len(batch)
        logger.debug("phase_f.step2: inserted batch of %d person_identifiers rows", len(batch))

    # ------------------------------------------------------------------
    # Step 3: target_group_membership
    # ------------------------------------------------------------------

    @classmethod
    def _step_target_group_membership(cls, db: Session, result: PhaseFPopulationResult) -> None:
        """Link every target_group_row that has a result to its person_master.

        Source: target_group_results JOIN person_master ON canonical_person_key.
        Each target_row_id may appear in multiple results (one per
        selected_service permutation), but target_group_membership.target_row_id
        has a UNIQUE constraint so only the first occurrence is inserted.

        ON CONFLICT (target_row_id) DO NOTHING for idempotency.
        """
        logger.info("phase_f.step3: populating target_group_membership")

        affected_rows = db.execute(
            text("""
                INSERT INTO target_group_membership
                    (person_id, target_row_id, group_job_id)
                SELECT DISTINCT ON (r.target_row_id)
                    pm.id           AS person_id,
                    r.target_row_id,
                    r.group_job_id
                FROM target_group_results r
                JOIN person_master pm
                  ON pm.canonical_person_key = r.canonical_person_key
                WHERE r.target_row_id IS NOT NULL
                  AND r.canonical_person_key IS NOT NULL
                ON CONFLICT (target_row_id) DO NOTHING
            """)
        ).rowcount

        result.target_group_membership_inserted = max(0, affected_rows)
        logger.info("phase_f.step3: %d rows inserted into target_group_membership", affected_rows)

        # Count skips as total eligible minus inserted.
        total_eligible: int = db.execute(
            text("""
                SELECT COUNT(DISTINCT r.target_row_id)
                FROM target_group_results r
                WHERE r.target_row_id IS NOT NULL
                  AND r.canonical_person_key IS NOT NULL
            """)
        ).scalar_one()
        result.target_group_membership_skipped = max(0, total_eligible - result.target_group_membership_inserted)

    # ------------------------------------------------------------------
    # Step 4: disease_screening_events
    # ------------------------------------------------------------------

    @classmethod
    def _step_disease_screening_events(cls, db: Session, result: PhaseFPopulationResult) -> None:
        """Link DiseaseScreeningRecord rows to person_master via CID.

        We match on:
            person_master.primary_cid = disease_screening_records.normalized_person_identifier

        Only records whose identifier is a 13-digit CID that matches a known
        person_master are linked.  Records with no person_master match are
        inserted with person_id = NULL (the column is nullable).

        ON CONFLICT (source_record_id) DO NOTHING for idempotency.
        """
        logger.info("phase_f.step4: populating disease_screening_events")

        # Single INSERT covering both matched and unmatched records.
        # Migration 0014 adds uq_dse_source_record_id unique index so ON CONFLICT works.
        # LEFT JOIN on person_master: person_id is NULL when no CID match found.
        matched_rows = db.execute(
            text("""
                INSERT INTO disease_screening_events
                    (person_id, source_record_id, normalized_service_key, event_date)
                SELECT
                    pm.id,
                    dsr.id,
                    dsr.normalized_service_key,
                    dsr.visit_date
                FROM disease_screening_records dsr
                LEFT JOIN person_master pm
                  ON pm.primary_cid = dsr.normalized_person_identifier
                ON CONFLICT (source_record_id) DO NOTHING
            """)
        ).rowcount

        result.disease_screening_events_inserted += max(0, matched_rows)
        logger.info("phase_f.step4: %d rows inserted (matched + unmatched)", matched_rows)

        unmatched_rows = 0

        # Skipped = already-existing rows that the ON CONFLICT clause blocked.
        total_records: int = db.execute(
            text("SELECT COUNT(*) FROM disease_screening_records")
        ).scalar_one()
        result.disease_screening_events_skipped = max(
            0, total_records - result.disease_screening_events_inserted
        )
