from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


BACKEND_ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from migrate_legacy_core_dry_run import (  # noqa: E402
    REQUIRED_TARGET_TABLES,
    _connect,
    _count,
    _json_default,
    _map_import_job,
    _map_patient,
    _map_target_group_job,
    _map_target_group_row,
    _target_schema_warnings,
)


MIGRATION_NAMESPACE = uuid.UUID("8f1ad025-9377-4d83-a6ac-68ed92a786b4")
CORE_TARGET_TABLES = (
    "import_jobs",
    "patients",
    "target_group_jobs",
    "target_group_job_files",
    "target_group_rows",
)


@dataclass
class ApplyState:
    import_job_id_map: dict[Any, uuid.UUID] = field(default_factory=dict)
    patient_id_map: dict[Any, uuid.UUID] = field(default_factory=dict)
    target_group_job_id_map: dict[Any, uuid.UUID] = field(default_factory=dict)
    target_group_job_file_id_map: dict[Any, uuid.UUID] = field(default_factory=dict)
    patient_pid_owner: dict[str, uuid.UUID] = field(default_factory=dict)
    patient_cid_owner: dict[str, uuid.UUID] = field(default_factory=dict)


def _deterministic_uuid(entity: str, legacy_id: Any) -> uuid.UUID:
    return uuid.uuid5(MIGRATION_NAMESPACE, f"{entity}:{legacy_id}")


def _fetch_all(conn, table_name: str, limit: int | None = None) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        if limit is None:
            cur.execute(f"select * from {table_name} order by created_at nulls last, id")
        else:
            cur.execute(f"select * from {table_name} order by created_at nulls last, id limit %s", (limit,))
        return list(cur.fetchall())


def _insert(cur, table_name: str, payload: dict[str, Any]) -> None:
    columns = list(payload)
    placeholders = ", ".join(["%s"] * len(columns))
    column_sql = ", ".join(columns)
    cur.execute(
        f"insert into {table_name} ({column_sql}) values ({placeholders})",
        [_adapt_value(payload[column]) for column in columns],
    )


def _insert_many(cur, table_name: str, payloads: list[dict[str, Any]]) -> None:
    if not payloads:
        return
    columns = list(payloads[0])
    placeholders = ", ".join(["%s"] * len(columns))
    column_sql = ", ".join(columns)
    cur.executemany(
        f"insert into {table_name} ({column_sql}) values ({placeholders})",
        [[_adapt_value(payload[column]) for column in columns] for payload in payloads],
    )


def _adapt_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return Jsonb(value)
    return value


def _target_is_empty(conn) -> tuple[bool, dict[str, int]]:
    counts = {table: _count(conn, table) for table in CORE_TARGET_TABLES}
    return all(count == 0 for count in counts.values()), counts


def _prepare_import_job(row: dict[str, Any], state: ApplyState) -> tuple[dict[str, Any], list[str]]:
    mapped, warnings = _map_import_job(row)
    new_id = _deterministic_uuid("import_jobs", row["id"])
    state.import_job_id_map[row["id"]] = new_id
    mapped["id"] = new_id
    return mapped, warnings


def _prepare_patient(row: dict[str, Any], state: ApplyState) -> tuple[dict[str, Any] | None, list[str]]:
    mapped = _map_patient(row)
    warnings: list[str] = []
    new_id = _deterministic_uuid("patients", row["id"])

    pid = mapped.get("pid")
    citizen_id = mapped.get("citizen_id")
    if pid and pid in state.patient_pid_owner:
        state.patient_id_map[row["id"]] = state.patient_pid_owner[pid]
        return None, [f"patients {row['id']}: duplicate pid; mapped to first migrated patient"]
    if citizen_id and citizen_id in state.patient_cid_owner:
        state.patient_id_map[row["id"]] = state.patient_cid_owner[citizen_id]
        return None, [f"patients {row['id']}: duplicate citizen_id; mapped to first migrated patient"]

    mapped["id"] = new_id
    mapped["source_import_job_id"] = state.import_job_id_map.get(row.get("source_import_job_id"))
    state.patient_id_map[row["id"]] = new_id
    if pid:
        state.patient_pid_owner[pid] = new_id
    if citizen_id:
        state.patient_cid_owner[citizen_id] = new_id
    return mapped, warnings


def _prepare_target_group_job(row: dict[str, Any], state: ApplyState) -> tuple[dict[str, Any], list[str]]:
    mapped, warnings = _map_target_group_job(row)
    new_id = _deterministic_uuid("target_group_jobs", row["id"])
    state.target_group_job_id_map[row["id"]] = new_id
    mapped["id"] = new_id
    mapped["import_job_id"] = state.import_job_id_map.get(row.get("import_job_id"))
    return mapped, warnings


def _prepare_target_group_job_file(row: dict[str, Any], state: ApplyState) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    group_job_id = state.target_group_job_id_map[row["id"]]
    new_id = _deterministic_uuid("target_group_job_files", row["id"])
    state.target_group_job_file_id_map[row["id"]] = new_id
    mapped_job, job_warnings = _map_target_group_job(row)
    warnings.extend(job_warnings)

    return (
        {
            "id": new_id,
            "group_job_id": group_job_id,
            "file_name": mapped_job["source_file_name"],
            "file_path": row.get("stored_path"),
            "file_type": mapped_job["source_file_type"],
            "sha256": mapped_job["source_file_hash"],
            "size_bytes": None,
            "source_modified_at": None,
            "parse_status": mapped_job["parse_status"],
            "row_count": mapped_job["total_rows"],
            "warning_count": mapped_job["warning_rows"],
            "error_message": None,
            "parse_error_summary": None,
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
        },
        warnings,
    )


def _prepare_target_group_row(row: dict[str, Any], state: ApplyState) -> tuple[dict[str, Any] | None, list[str]]:
    warnings: list[str] = []
    legacy_job_id = row.get("job_id")
    group_job_id = state.target_group_job_id_map.get(legacy_job_id)
    source_file_id = state.target_group_job_file_id_map.get(legacy_job_id)
    if not group_job_id or not source_file_id:
        return None, [f"target_group_rows {row['id']}: missing migrated target group job/file; skipped"]

    mapped, map_warnings = _map_target_group_row(row, job_file_placeholder=str(source_file_id))
    warnings.extend(map_warnings)

    mapped["id"] = _deterministic_uuid("target_group_rows", row["id"])
    mapped["group_job_id"] = group_job_id
    mapped["source_file_id"] = source_file_id
    mapped["matched_patient_id"] = state.patient_id_map.get(row.get("matched_patient_id"))
    if mapped["source_file_name"] is None:
        mapped["source_file_name"] = None
    return mapped, warnings


def _apply_table(
    cur,
    rows: list[dict[str, Any]],
    table_name: str,
    prepare,
    state: ApplyState,
) -> dict[str, Any]:
    skipped = 0
    warnings: list[str] = []
    payloads: list[dict[str, Any]] = []
    for row in rows:
        payload, row_warnings = prepare(row, state)
        warnings.extend(row_warnings)
        if payload is None:
            skipped += 1
            continue
        payloads.append(payload)
    _insert_many(cur, table_name, payloads)
    return {
        "legacy_rows": len(rows),
        "inserted": len(payloads),
        "skipped": skipped,
        "warnings": warnings[:50],
        "warning_count": len(warnings),
    }


def run_migration(
    legacy_url: str,
    target_url: str,
    execute: bool,
    allow_non_empty: bool,
    limit: int | None,
) -> dict[str, Any]:
    if legacy_url == target_url:
        raise ValueError("legacy and target database URLs must not be the same")

    with _connect(legacy_url) as legacy_conn, _connect(target_url) as target_conn:
        schema_warnings = _target_schema_warnings(target_conn)
        if schema_warnings:
            raise ValueError(f"target schema is not ready: {schema_warnings}")

        target_empty, target_counts_before = _target_is_empty(target_conn)
        if not target_empty and not allow_non_empty:
            raise ValueError(f"target core tables are not empty: {target_counts_before}")

        state = ApplyState()
        report: dict[str, Any] = {
            "mode": "execute" if execute else "dry_run_rollback",
            "writes_committed": False,
            "legacy_url_safe": legacy_url.rsplit("@", 1)[-1],
            "target_url_safe": target_url.rsplit("@", 1)[-1],
            "target_counts_before": target_counts_before,
            "tables": {},
        }

        try:
            with target_conn.cursor() as cur:
                report["tables"]["import_jobs"] = _apply_table(
                    cur,
                    _fetch_all(legacy_conn, "import_jobs", limit),
                    "import_jobs",
                    _prepare_import_job,
                    state,
                )
                report["tables"]["patients"] = _apply_table(
                    cur,
                    _fetch_all(legacy_conn, "patients", limit),
                    "patients",
                    _prepare_patient,
                    state,
                )
                target_group_job_rows = _fetch_all(legacy_conn, "target_group_jobs", limit)
                report["tables"]["target_group_jobs"] = _apply_table(
                    cur,
                    target_group_job_rows,
                    "target_group_jobs",
                    _prepare_target_group_job,
                    state,
                )
                report["tables"]["target_group_job_files"] = _apply_table(
                    cur,
                    target_group_job_rows,
                    "target_group_job_files",
                    _prepare_target_group_job_file,
                    state,
                )
                report["tables"]["target_group_rows"] = _apply_table(
                    cur,
                    _fetch_all(legacy_conn, "target_group_rows", limit),
                    "target_group_rows",
                    _prepare_target_group_row,
                    state,
                )

            if execute:
                target_conn.commit()
                report["writes_committed"] = True
            else:
                target_conn.rollback()
                report["rollback_reason"] = "default dry-run rollback; pass --execute to commit"

        except Exception:
            target_conn.rollback()
            raise

        _, target_counts_after = _target_is_empty(target_conn)
        report["target_counts_after"] = target_counts_after
        report["id_map_counts"] = {
            "import_jobs": len(state.import_job_id_map),
            "patients": len(state.patient_id_map),
            "target_group_jobs": len(state.target_group_job_id_map),
            "target_group_job_files": len(state.target_group_job_file_id_map),
        }
        report["deferred_tables"] = {
            "diagnosis_history": "not applied in core v1",
            "disease_screening_records": "not applied in core v1",
            "target_group_sheets": "prefer re-inspecting original files",
            "target_group_history_rows": "prefer re-ingesting original files",
            "target_group_results": "regenerate with current business logic",
        }
        return report


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Apply legacy core migration into a fresh current-schema DB")
    parser.add_argument("--legacy-url", default=os.environ.get("LEGACY_DATABASE_URL"))
    parser.add_argument("--target-url", default=os.environ.get("TARGET_DATABASE_URL"))
    parser.add_argument("--execute", action="store_true", help="Commit writes. Default rolls back.")
    parser.add_argument("--allow-non-empty", action="store_true", help="Allow target core tables to contain rows.")
    parser.add_argument("--limit", type=int, default=None, help="Limit rows read per legacy table for smoke tests.")
    args = parser.parse_args()

    if not args.legacy_url:
        raise SystemExit("Missing --legacy-url or LEGACY_DATABASE_URL")
    if not args.target_url:
        raise SystemExit("Missing --target-url or TARGET_DATABASE_URL")

    report = run_migration(
        legacy_url=args.legacy_url,
        target_url=args.target_url,
        execute=args.execute,
        allow_non_empty=args.allow_non_empty,
        limit=args.limit if args.limit and args.limit > 0 else None,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, default=_json_default))


if __name__ == "__main__":
    main()
