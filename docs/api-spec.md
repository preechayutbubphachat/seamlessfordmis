# API Spec Draft

## System
- `GET /api/v1/system/status`
- `GET /api/v1/source/check`
- `POST /api/v1/source/sync`

## Target Groups
- `POST /api/v1/target-groups/upload`
- `POST /api/v1/target-groups/{job_id}/confirm`
- `POST /api/v1/target-groups/{job_id}/match`
- `POST /api/v1/target-groups/{job_id}/results`
- `POST /api/v1/target-groups/{job_id}/export`

## Patients
- `GET /api/v1/patients/search`
- `GET /api/v1/patients/{patient_id}/history`

หมายเหตุ:
- MVP รองรับ Excel เท่านั้น
- PDF parser เป็น TODO แยก service/importer ไว้รองรับเฟสถัดไป
