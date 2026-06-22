# seamlessfordmis

Internal hospital-safe web application for importing, validating, matching, and reporting against the disease screening database (`ฐานข้อมูลการตรวจโรค`) and target group files.

## Core capabilities

- staging-first import pipeline for disease screening source files
- staging-first import pipeline for target group uploads
- normalization and validation for identifiers, names, services, and dates
- matching by normalized identifier with conservative fallback rules
- target group result generation for selected diseases/services
- business-readable summary and person-level outputs
- export/reporting for downstream hospital operations

## Repository structure

```text
backend/
frontend/
docs/
data/
uploads/
logs/
```

## Local setup

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m alembic upgrade head
uvicorn app.main:app --reload --host 127.0.0.1 --port 8010
```

Backend environment example:

```env
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/hospital_group_history
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend environment example:

```env
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8010
```

## Main endpoints

- `GET /api/system/status`
- `POST /api/system/check-source-update`
- `POST /api/system/sync-main-dataset`
- `POST /api/target-groups/upload`
- `POST /api/target-groups/{group_id}/generate-results`
- `GET /api/target-groups/{group_id}/results`
- `GET /api/target-groups/{group_id}/result-summary`
- `GET /api/target-groups/{group_id}/export`

## Safety rules

- preserve raw source values before normalization
- do not silently guess missing identifiers
- invalid rows remain visible in staging
- do not merge invalid staging rows into production tables
- ambiguous matches must not be auto-resolved
- missing history is not the same as invalid identifier

## Notes

- Excel import is the current MVP path
- PDF support remains staged and should stay reviewable
- provenance and auditability are required for hospital operations
- if your existing database predates the current `backend/alembic` chain, do not run in-place upgrades blindly; follow [docs/legacy-db-migration-strategy.md](C:/2025/web-69/โรงบาลหนองพอก/seamlessfordmis/docs/legacy-db-migration-strategy.md)
