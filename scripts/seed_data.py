import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete

from app.db.session import SessionLocal
from app.models.disease_mapping import DiseaseMapping


def main() -> None:
    seed_path = Path("seed/disease_mapping_seed.json")
    payload = json.loads(seed_path.read_text(encoding="utf-8"))

    with SessionLocal() as db:
        # Seed disease mappings only. Imported patient/history data must remain intact.
        db.execute(delete(DiseaseMapping))
        for row in payload:
            db.add(DiseaseMapping(**row))
        db.commit()


if __name__ == "__main__":
    main()
