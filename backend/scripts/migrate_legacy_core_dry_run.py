from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

import psycopg
from psycopg.rows import dict_row


BACKEND_ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.field_mapping_service import FieldMappingService  # noqa: E402
from app.utils.text_normalization import normalize_text  # noqa: E402


CORE_TABLES = ("patients", "import_jobs", "target_group_jobs", "target_group_rows")
REQUIRED_TARGET_TABLES = (
    "patients",
    "import_jobs",
    "target_group_jobs",
    "target_group_job_files",
    "target_group_rows",
)


@dataclass
class TablePlan:
    legacy_count: int = 0
    target_count: int | None = None
    status: str = "pending"
    warnings: list[str] = field(default_factory=list)
    sample_transformed_rows: list[dict[str, Any]] = field(default_factory=list)


def _json_default(value: object) -> str | None:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if value is None:
        return None
    return str(value)


def _connect(url: str):
    return psycopg.connect(url, row_factory=dict_row)


def _table_exists(conn, table_name: str) -> bool:
    with conn.cursor() as cur:
        cur.execute("select to_regclass(%s) as table_name", (f"public.{table_name}",))
        row = cur.fetchone()
        return bool(row and row["table_name"])


def _columns(conn, table_name: str) -> set[str]:
    if not _table_exists(conn, table_name):
        return set()
    with conn.cursor() as cur:
        cur.execute(
            """
            select column_name
            from information_schema.columns
            where table_schema = 'public' and table_name = %s
            order by ordinal_position
            """,
            (table_name,),
        )
        return {row["column_name"] for row in cur.fetchall()}


def _count(conn, table_name: str) -> int:
    if not _table_exists(conn, table_name):
        return 0
    with conn.cursor() as cur:
        cur.execute(f"select count(*) as count from {table_name}")
        return int(cur.fetchone()["count"])


def _sample(conn, table_name: str, limit: int) -> list[dict[str, Any]]:
    if not _table_exists(conn, table_name):
        return []
    with conn.cursor() as cur:
        cur.execute(f"select * from {table_name} order by created_at nulls last, id limit %s", (limit,))
        return list(cur.fetchall())


def _status_from_legacy(*values: Any) -> str:
    for value in values:
        text = normalize_text(value)
        if text:
            lowered = text.casefold()
            if lowered in {"success", "completed", "parsed", "confirmed"}:
                return "success"
            if lowered in {"warning", "needs_review", "review"}:
                return "warning"
            if lowered in {"failed", "error"}:
                return "failed"
            if lowered in {"processing", "pending"}:
                return lowered
            return text
    return "pending"


def _legacy_file_type(filename: object | None, explicit: object | None) -> str:
    explicit_text = normalize_text(explicit)
    if explicit_text:
        lowered = explicit_text.casefold()
        if lowered in {"excel", "xlsx", "xls", "csv", "pdf"}:
            return "excel" if lowered in {"xlsx", "xls"} else lowered

    filename_text = normalize_text(filename) or ""
    suffix = filename_text.rsplit(".", 1)[-1].casefold() if "." in filename_text else ""
    if suffix in {"xlsx", "xls"}:
        return "excel"
    if suffix == "csv":
        return "csv"
    if suffix == "pdf":
        return "pdf"
    return "excel"


def _hash_or_placeholder(value: object | None, warnings: list[str], context: str) -> str:
    text = normalize_text(value)
    if text and len(text) == 64:
        return text
    warnings.append(f"{context}: missing or invalid sha256; dry-run would require recomputing from source file")
    return "0" * 64


def _map_patient(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row.get("id"),
        "pid": normalize_text(row.get("pid")),
        "citizen_id": normalize_text(row.get("citizen_id")),
        "hn": normalize_text(row.get("hn")),
        "full_name": normalize_text(row.get("full_name")) or "UNKNOWN_LEGACY_PATIENT",
        "birth_date": row.get("birth_date"),
        "sex": None,
        "source_import_job_id": row.get("source_import_job_id"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def _map_import_job(row: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    imported_rows = int(row.get("imported_rows") or 0)
    error_rows = int(row.get("error_rows") or 0)
    total_rows = int(row.get("total_rows") or imported_rows + error_rows or 0)

    return (
        {
            "id": row.get("id"),
            "source_type": normalize_text(row.get("job_type")) or "legacy_import",
            "source_file_name": normalize_text(row.get("source_filename")) or f"legacy-import-{row.get('id')}",
            "source_file_path": normalize_text(row.get("source_path")),
            "source_file_hash": _hash_or_placeholder(row.get("source_hash_sha256"), warnings, "import_jobs"),
            "source_set_hash": normalize_text(row.get("source_manifest_hash_sha256")),
            "source_file_count": int(row.get("source_file_count") or 1),
            "source_file_size": row.get("source_size_bytes"),
            "source_file_modified_at": row.get("source_modified_at"),
            "status": _status_from_legacy(row.get("status")),
            "total_rows": total_rows,
            "parsed_rows": imported_rows + error_rows if imported_rows or error_rows else total_rows,
            "valid_rows": imported_rows,
            "invalid_rows": error_rows,
            "warning_rows": 0,
            "merged_rows": imported_rows,
            "skipped_rows": 0,
            "duplicate_identifier_count": 0,
            "success_rows": imported_rows,
            "failed_rows": error_rows,
            "started_at": row.get("started_at"),
            "finished_at": row.get("completed_at"),
            "created_by": None,
            "error_summary": normalize_text(row.get("error_message")),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
        },
        warnings,
    )


def _map_target_group_job(row: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    total_rows = int(row.get("total_rows") or 0)
    valid_rows = int(row.get("valid_rows") or 0)
    invalid_rows = int(row.get("invalid_rows") or 0)
    review_rows = int(row.get("review_rows") or 0)
    source_file_name = normalize_text(row.get("original_filename")) or normalize_text(row.get("stored_path")) or f"legacy-target-group-{row.get('id')}"

    return (
        {
            "id": row.get("id"),
            "import_job_id": row.get("import_job_id"),
            "group_name": normalize_text(row.get("group_name")) or f"Legacy target group {row.get('id')}",
            "source_file_name": source_file_name,
            "source_file_type": _legacy_file_type(source_file_name, row.get("source_file_type")),
            "source_file_hash": _hash_or_placeholder(row.get("file_hash_sha256"), warnings, "target_group_jobs"),
            "source_set_hash": normalize_text(row.get("file_hash_sha256")),
            "source_file_count": 1,
            "uploaded_by": normalize_text(row.get("uploaded_by")),
            "parse_status": _status_from_legacy(row.get("parse_status"), row.get("status")),
            "match_status": _status_from_legacy(row.get("match_status")),
            "total_rows": total_rows,
            "parsed_rows": total_rows,
            "valid_rows": valid_rows,
            "invalid_rows": invalid_rows,
            "missing_cid_rows": 0,
            "duplicate_cid_rows": 0,
            "warning_rows": review_rows,
            "failed_rows": 0,
            "notes": "; ".join(
                part
                for part in (
                    normalize_text(row.get("notes")),
                    "migrated_from_legacy_target_group_jobs",
                    "missing/duplicate CID counts must be recomputed from migrated rows",
                )
                if part
            ),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
        },
        warnings,
    )


def _safe_raw_payload(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if value is None:
        return {}
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {"legacy_raw_payload_text": value}
        return parsed if isinstance(parsed, dict) else {"legacy_raw_payload": parsed}
    return {"legacy_raw_payload": value}


def _map_target_group_row(row: dict[str, Any], job_file_placeholder: str = "DRY_RUN_SOURCE_FILE_ID") -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    raw_payload = _safe_raw_payload(row.get("raw_payload"))
    payload = {
        **raw_payload,
        "CID": row.get("citizen_id") or raw_payload.get("CID") or raw_payload.get("cid"),
        "citizen_id": row.get("citizen_id"),
        "pid": row.get("pid"),
        "hn": row.get("hn"),
        "full_name": row.get("full_name"),
        "birth_date": row.get("birth_date"),
    }
    normalized = FieldMappingService.map_target_group_row(payload)
    is_valid = row.get("is_valid")
    validation_status = "valid" if is_valid is True else "invalid" if is_valid is False else "warning"
    validation_errors = row.get("validation_errors")
    if validation_errors:
        validation_status = "invalid"

    if normalized["cid_validation_status"] != "valid_identifier":
        warnings.append(f"target_group_rows {row.get('id')}: CID status {normalized['cid_validation_status']}")

    return (
        {
            "id": row.get("id"),
            "group_job_id": row.get("job_id"),
            "source_file_id": job_file_placeholder,
            "source_file_name": None,
            "row_no": row.get("row_number") or 0,
            "source_row_no": row.get("row_number"),
            "raw_cid": normalized["raw_cid"],
            "raw_pid": normalize_text(row.get("pid")),
            "raw_citizen_id": normalize_text(row.get("citizen_id")),
            "raw_hn": normalized["raw_hn"],
            "raw_full_name": normalized["raw_full_name"],
            "raw_birth_date": normalized["raw_birth_date"],
            "raw_age": normalized["raw_age"],
            "raw_sex": normalized["raw_sex"],
            "raw_target_history_labels": normalized["raw_target_history_labels"],
            "raw_target_history_note": normalized["raw_target_history_note"],
            "raw_target_history_last_visit_date": normalized["raw_target_history_last_visit_date"],
            "normalized_cid": normalized["normalized_cid"],
            "normalized_pid": None,
            "normalized_citizen_id": normalized["normalized_citizen_id"],
            "normalized_hn": normalized["normalized_hn"],
            "normalized_full_name": normalized["normalized_full_name"],
            "normalized_birth_date": normalized["normalized_birth_date"],
            "normalized_age": normalized["normalized_age"],
            "normalized_sex": normalized["normalized_sex"],
            "normalized_target_history_service_keys": normalized["normalized_target_history_service_keys"],
            "normalized_target_history_last_visit_date": normalized["normalized_target_history_last_visit_date"],
            "parse_status": _status_from_legacy(row.get("parse_status"), "parsed"),
            "validation_status": validation_status,
            "cid_validation_status": normalized["cid_validation_status"],
            "duplicate_status": "requires_recompute",
            "match_status": _status_from_legacy(row.get("match_status")),
            "match_method": None,
            "matched_patient_id": row.get("matched_patient_id"),
            "matched_identifier_basis": None,
            "matched_name_basis": None,
            "confidence_flag": normalize_text(row.get("confidence_flag")),
            "error_message": normalize_text(row.get("error_message")) or normalize_text(validation_errors),
            "warning_message": "duplicate status must be recomputed after migration",
            "raw_json": {
                **raw_payload,
                "legacy_row_id": str(row.get("id")),
                "legacy_job_id": str(row.get("job_id")),
                "legacy_row_number": row.get("row_number"),
                "migration_note": "dry-run transform from legacy target_group_rows",
            },
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
        },
        warnings,
    )


def _plan_table(
    legacy_conn,
    target_conn,
    table_name: str,
    mapper,
    sample_size: int,
) -> TablePlan:
    plan = TablePlan(
        legacy_count=_count(legacy_conn, table_name),
        target_count=_count(target_conn, table_name),
        status="dry_run_only",
    )
    if plan.target_count:
        plan.warnings.append(f"target table {table_name} is not empty ({plan.target_count} rows); apply script must refuse unless --allow-non-empty is explicit")

    for row in _sample(legacy_conn, table_name, sample_size):
        mapped = mapper(row)
        if isinstance(mapped, tuple):
            transformed, warnings = mapped
            plan.warnings.extend(warnings)
        else:
            transformed = mapped
        plan.sample_transformed_rows.append(transformed)

    return plan


def _target_schema_warnings(target_conn) -> list[str]:
    warnings: list[str] = []
    for table_name in REQUIRED_TARGET_TABLES:
        if not _table_exists(target_conn, table_name):
            warnings.append(f"target database is missing required current-schema table: {table_name}")
    return warnings


def build_plan(legacy_url: str, target_url: str, sample_size: int) -> dict[str, Any]:
    if legacy_url == target_url:
        raise ValueError("legacy and target database URLs must not be the same")

    with _connect(legacy_url) as legacy_conn, _connect(target_url) as target_conn:
        plan = {
            "mode": "dry_run",
            "writes_performed": False,
            "legacy_url_safe": legacy_url.rsplit("@", 1)[-1],
            "target_url_safe": target_url.rsplit("@", 1)[-1],
            "target_schema_warnings": _target_schema_warnings(target_conn),
            "tables": {
                "patients": _plan_table(legacy_conn, target_conn, "patients", _map_patient, sample_size).__dict__,
                "import_jobs": _plan_table(legacy_conn, target_conn, "import_jobs", _map_import_job, sample_size).__dict__,
                "target_group_jobs": _plan_table(
                    legacy_conn,
                    target_conn,
                    "target_group_jobs",
                    _map_target_group_job,
                    sample_size,
                ).__dict__,
                "target_group_rows": _plan_table(
                    legacy_conn,
                    target_conn,
                    "target_group_rows",
                    _map_target_group_row,
                    sample_size,
                ).__dict__,
            },
            "deferred_tables": {
                "target_group_results": "archive or regenerate; do not migrate as active current results in core dry-run",
                "diagnosis_history": "next dry-run phase with disease_screening_records derivation",
                "target_group_history_rows": "prefer re-ingesting original target files with current multi-sheet importer",
            },
        }
    return plan


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Dry-run legacy core migration mapping into a fresh current-schema DB")
    parser.add_argument("--legacy-url", default=os.environ.get("LEGACY_DATABASE_URL"))
    parser.add_argument("--target-url", default=os.environ.get("TARGET_DATABASE_URL"))
    parser.add_argument("--sample-size", type=int, default=3)
    args = parser.parse_args()

    if not args.legacy_url:
        raise SystemExit("Missing --legacy-url or LEGACY_DATABASE_URL")
    if not args.target_url:
        raise SystemExit("Missing --target-url or TARGET_DATABASE_URL")

    plan = build_plan(args.legacy_url, args.target_url, max(args.sample_size, 0))
    print(json.dumps(plan, ensure_ascii=False, indent=2, default=_json_default))


if __name__ == "__main__":
    main()
