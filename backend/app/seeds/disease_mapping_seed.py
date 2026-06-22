import json
import logging
from pathlib import Path

from sqlalchemy import delete, func, select

from app.db.session import SessionLocal
from app.models.disease_mapping import DiseaseMapping


logger = logging.getLogger(__name__)


FALLBACK_ROWS = [
    {
        "raw_code": None,
        "raw_name": "คัดกรองมะเร็งปากมดลูก",
        "normalized_key": "cervical_screen",
        "normalized_label": "คัดกรองมะเร็งปากมดลูก",
        "icd10_code": "Z124",
        "is_active": True,
    },
    {
        "raw_code": None,
        "raw_name": "ตรวจ HPV",
        "normalized_key": "hpv_screen",
        "normalized_label": "ตรวจ HPV",
        "icd10_code": None,
        "is_active": True,
    },
    {
        "raw_code": None,
        "raw_name": "ตรวจน้ำตาล FPG",
        "normalized_key": "dm_screen_fpg",
        "normalized_label": "คัดกรองเบาหวาน (FPG)",
        "icd10_code": None,
        "is_active": True,
    },
]


def load_seed_rows() -> list[dict]:
    shared_seed = Path(__file__).resolve().parents[3] / "seed" / "disease_mapping_seed.json"
    if not shared_seed.exists():
        return FALLBACK_ROWS

    payload = json.loads(shared_seed.read_text(encoding="utf-8"))
    rows: list[dict] = []
    for item in payload:
        rows.append(
            {
                "raw_code": item.get("diagnosis_code"),
                "raw_name": item.get("disease_name_raw"),
                "normalized_key": item["normalized_disease_key"],
                "normalized_label": item["disease_group_label"],
                "icd10_code": item.get("diagnosis_code"),
                "is_active": True,
            }
        )
    return rows


def seed_disease_mapping_if_empty() -> int:
    """Seed the disease/service catalog ONLY when the table is empty.

    Idempotent and non-destructive: never deletes existing rows, so it is safe to
    call on every startup. Used by the desktop bootstrap so the "สร้างผลลัพธ์"
    page has disease/service options on a fresh SQLite database (the options come
    from disease_mapping, a seeded reference catalog — NOT from screening import).

    Returns the number of rows inserted (0 if the table already had data).
    """
    with SessionLocal() as db:
        existing = db.scalar(select(func.count()).select_from(DiseaseMapping)) or 0
        if existing:
            return 0
        rows = load_seed_rows()
        for row in rows:
            db.add(DiseaseMapping(**row))
        db.commit()
        logger.info("disease_mapping.seeded_if_empty inserted=%s", len(rows))
        return len(rows)


def main() -> None:
    with SessionLocal() as db:
        db.execute(delete(DiseaseMapping))
        for row in load_seed_rows():
            db.add(DiseaseMapping(**row))
        db.commit()


if __name__ == "__main__":
    main()
