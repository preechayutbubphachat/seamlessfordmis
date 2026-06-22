import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text

from app.db.session import SessionLocal


def main() -> None:
    output_path = Path("seed/disease_mapping_coverage_report.json")

    with SessionLocal() as db:
        rows = db.execute(
            text(
                """
                select
                    disease_name_raw,
                    count(*) as history_row_count,
                    min(normalized_disease_key) as currently_resolved_key
                from diagnosis_history
                where disease_name_raw is not null and btrim(disease_name_raw) <> ''
                group by disease_name_raw
                order by count(*) desc, disease_name_raw asc
                """
            )
        ).mappings().all()

        mapping_rows = db.execute(
            text(
                """
                select
                    disease_name_raw,
                    normalized_disease_key,
                    disease_group_label
                from disease_mapping
                where disease_name_raw is not null and btrim(disease_name_raw) <> ''
                order by disease_group_label asc, disease_name_raw asc
                """
            )
        ).mappings().all()

    by_raw_name = {
        row["disease_name_raw"]: {
            "normalized_disease_key": row["normalized_disease_key"],
            "disease_group_label": row["disease_group_label"],
        }
        for row in mapping_rows
    }

    report = []
    for row in rows:
        raw_name = row["disease_name_raw"]
        mapped = by_raw_name.get(raw_name)
        report.append(
            {
                "disease_name_raw": raw_name,
                "history_row_count": int(row["history_row_count"]),
                "mapped": mapped is not None,
                "normalized_disease_key": mapped["normalized_disease_key"] if mapped else None,
                "disease_group_label": mapped["disease_group_label"] if mapped else None,
                "currently_resolved_key": row["currently_resolved_key"],
            }
        )

    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    mapped_count = sum(1 for item in report if item["mapped"])
    print(f"Wrote {output_path} with {mapped_count}/{len(report)} mapped service items.")


if __name__ == "__main__":
    main()
