CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE import_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_type VARCHAR(50) NOT NULL,
    source_file_name TEXT NOT NULL,
    source_file_path TEXT,
    source_file_hash CHAR(64) NOT NULL,
    source_file_size BIGINT,
    source_file_modified_at TIMESTAMP NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'pending',
    total_rows INTEGER NOT NULL DEFAULT 0,
    success_rows INTEGER NOT NULL DEFAULT 0,
    failed_rows INTEGER NOT NULL DEFAULT 0,
    started_at TIMESTAMP NULL,
    finished_at TIMESTAMP NULL,
    created_by TEXT NULL,
    error_summary TEXT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_import_jobs_source_type ON import_jobs(source_type);
CREATE INDEX idx_import_jobs_status ON import_jobs(status);
CREATE INDEX idx_import_jobs_hash ON import_jobs(source_file_hash);

CREATE TABLE staging_history_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    import_job_id UUID NOT NULL REFERENCES import_jobs(id) ON DELETE CASCADE,
    row_no INTEGER NOT NULL,
    raw_pid TEXT NULL,
    raw_citizen_id TEXT NULL,
    raw_hn TEXT NULL,
    raw_full_name TEXT NULL,
    raw_birth_date TEXT NULL,
    raw_visit_date TEXT NULL,
    raw_diagnosis_code TEXT NULL,
    raw_diagnosis_name TEXT NULL,
    raw_department TEXT NULL,
    raw_doctor_name TEXT NULL,
    parse_status VARCHAR(30) NOT NULL DEFAULT 'pending',
    validation_status VARCHAR(30) NOT NULL DEFAULT 'pending',
    error_message TEXT NULL,
    normalized_pid TEXT NULL,
    normalized_citizen_id TEXT NULL,
    normalized_hn TEXT NULL,
    normalized_full_name TEXT NULL,
    normalized_birth_date DATE NULL,
    normalized_visit_date DATE NULL,
    normalized_diagnosis_code TEXT NULL,
    normalized_diagnosis_name TEXT NULL,
    normalized_disease_key TEXT NULL,
    raw_json JSONB NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_staging_history_import_job_id ON staging_history_records(import_job_id);
CREATE INDEX idx_staging_history_validation_status ON staging_history_records(validation_status);

CREATE TABLE patients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pid TEXT NULL,
    citizen_id TEXT NULL,
    hn TEXT NULL,
    full_name TEXT NOT NULL,
    birth_date DATE NULL,
    sex VARCHAR(20) NULL,
    source_import_job_id UUID NULL REFERENCES import_jobs(id),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX uq_patients_pid ON patients(pid) WHERE pid IS NOT NULL;
CREATE UNIQUE INDEX uq_patients_citizen_id ON patients(citizen_id) WHERE citizen_id IS NOT NULL;
CREATE INDEX idx_patients_hn ON patients(hn);
CREATE INDEX idx_patients_full_name ON patients(full_name);
CREATE INDEX idx_patients_birth_date ON patients(birth_date);

CREATE TABLE diagnosis_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    visit_date DATE NOT NULL,
    diagnosis_code TEXT NULL,
    diagnosis_name TEXT NULL,
    normalized_disease_key TEXT NULL,
    department TEXT NULL,
    doctor_name TEXT NULL,
    source_import_job_id UUID NULL REFERENCES import_jobs(id),
    source_row_no INTEGER NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_diagnosis_history_patient_id ON diagnosis_history(patient_id);
CREATE INDEX idx_diagnosis_history_visit_date ON diagnosis_history(visit_date);
CREATE INDEX idx_diagnosis_history_diagnosis_code ON diagnosis_history(diagnosis_code);
CREATE INDEX idx_diagnosis_history_disease_key ON diagnosis_history(normalized_disease_key);

CREATE TABLE target_group_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    import_job_id UUID NULL REFERENCES import_jobs(id) ON DELETE SET NULL,
    group_name TEXT NOT NULL,
    source_file_name TEXT NOT NULL,
    source_file_type VARCHAR(20) NOT NULL,
    source_file_hash CHAR(64) NOT NULL,
    uploaded_by TEXT NULL,
    parse_status VARCHAR(30) NOT NULL DEFAULT 'pending',
    match_status VARCHAR(30) NOT NULL DEFAULT 'pending',
    notes TEXT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE target_group_rows (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    group_job_id UUID NOT NULL REFERENCES target_group_jobs(id) ON DELETE CASCADE,
    row_no INTEGER NOT NULL,
    raw_pid TEXT NULL,
    raw_citizen_id TEXT NULL,
    raw_hn TEXT NULL,
    raw_full_name TEXT NULL,
    raw_birth_date TEXT NULL,
    normalized_pid TEXT NULL,
    normalized_citizen_id TEXT NULL,
    normalized_hn TEXT NULL,
    normalized_full_name TEXT NULL,
    normalized_birth_date DATE NULL,
    parse_status VARCHAR(30) NOT NULL DEFAULT 'pending',
    match_status VARCHAR(30) NOT NULL DEFAULT 'pending',
    matched_patient_id UUID NULL REFERENCES patients(id) ON DELETE SET NULL,
    confidence_flag VARCHAR(30) NULL,
    error_message TEXT NULL,
    raw_json JSONB NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE target_group_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    group_job_id UUID NOT NULL REFERENCES target_group_jobs(id) ON DELETE CASCADE,
    patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    disease_key TEXT NOT NULL,
    disease_code TEXT NULL,
    disease_name TEXT NULL,
    last_visit_date DATE NULL,
    visit_count INTEGER NOT NULL DEFAULT 0,
    days_since_last_visit INTEGER NULL,
    years_since_last_visit NUMERIC(10, 2) NULL,
    result_status VARCHAR(30) NOT NULL DEFAULT 'generated',
    generated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor TEXT NULL,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    old_value_json JSONB NULL,
    new_value_json JSONB NULL,
    ip_address TEXT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE disease_mapping (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    raw_code TEXT NULL,
    raw_name TEXT NULL,
    normalized_key TEXT NOT NULL,
    normalized_label TEXT NOT NULL,
    icd10_code TEXT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
