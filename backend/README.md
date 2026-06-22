# Backend Setup

Backend นี้เป็น FastAPI + SQLAlchemy 2.0 + PostgreSQL สำหรับงาน hospital operations ภายใน

## จุดเน้นของโครงนี้

- ตรวจการเปลี่ยนแปลงไฟล์ต้นทางด้วย `SHA-256`
- import แบบ staging-first
- เก็บ raw rows และ validation errors เพื่อ audit ย้อนหลัง
- match ผู้ป่วยตามลำดับ `PID -> citizen ID -> HN -> name + birth date -> name only`
- มี TODO marker สำหรับ PDF import ในเฟสถัดไป

## โครง API หลัก

- `GET /api/system/status`
- `POST /api/system/check-source-update`
- `POST /api/system/sync-main-dataset`
- `POST /api/target-groups/upload`
- `POST /api/target-groups/{group_id}/confirm-import`
- `POST /api/target-groups/{group_id}/run-match`
- `POST /api/target-groups/{group_id}/generate-results`
- `GET /api/target-groups/{group_id}/results`
- `GET /api/patients/search`
- `GET /api/patients/{patient_id}/history`
- `GET /api/target-groups/{group_id}/export`

## ติดตั้ง

```bash
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
```

ตั้งค่า `.env`

```env
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/hospital_group_history
```

## สร้าง schema

```bash
python -m alembic upgrade head
python -m app.seeds.disease_mapping_seed
```

## รัน API

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8010
```

## รันทดสอบ

```bash
pytest
```

## หมายเหตุสำคัญ

- current scaffold เน้น database layer + service structure ที่ชัดและปลอดภัยก่อน
- importer จริงสำหรับโครง Excel หน้างานควร review mapping column อีกครั้งก่อน production
- PDF import ยังไม่เปิดใน MVP และจะต้องมี review workflow ก่อนใช้กับเอกสาร scan
