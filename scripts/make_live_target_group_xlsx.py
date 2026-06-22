import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal
from app.models.patient import Patient


def main() -> None:
    target = Path("data/samples/live_target_group.xlsx")
    with SessionLocal() as db:
        patients = db.scalars(select(Patient).where(Patient.pid.is_not(None)).order_by(Patient.id.asc()).limit(5)).all()

    rows = [
        {
            "pid": patient.pid,
            "citizen_id": patient.citizen_id,
            "hn": patient.hn,
            "full_name": patient.full_name,
            "birth_date": patient.birth_date.isoformat() if patient.birth_date else None,
        }
        for patient in patients
    ]
    rows.append(
        {
            "pid": None,
            "citizen_id": None,
            "hn": None,
            "full_name": "Unmatched Demo Patient",
            "birth_date": "1990-01-01",
        }
    )

    target.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_excel(target, index=False)
    print("created live_target_group.xlsx")


if __name__ == "__main__":
    main()
