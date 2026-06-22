export type DatasetStatus = {
  dataset_ready: boolean;
  source_file_exists: boolean;
  source_file_changed: boolean;
  source_file_count: number;
  manifest_hash_sha256: string | null;
  import_status: string | null;
  last_completed_import_job_id: number | null;
  row_counts: {
    patients: number;
    diagnosis_history: number;
  };
  fingerprint: {
    filename: string;
    sha256: string;
    modified_at: string;
    size_bytes: number;
    path: string;
  } | null;
};

export type SyncResponse = {
  job_id: number;
  status: string;
  total_rows: number;
  imported_rows: number;
  error_rows: number;
  fingerprint: {
    filename: string;
    sha256: string;
    modified_at: string;
    size_bytes: number;
    path: string;
  };
  manifest_hash_sha256: string;
  file_count: number;
  validation_issues: ValidationIssue[];
};

export type ValidationIssue = {
  row_number: number;
  field: string;
  message: string;
};

export type TargetGroupUploadResponse = {
  job_id: number;
  group_name: string;
  status: string;
  total_rows: number;
  valid_rows: number;
  invalid_rows: number;
  preview_rows: Record<string, string | number | null>[];
  validation_issues: ValidationIssue[];
  uploaded_at: string;
};

export type TargetGroupJob = {
  job_id: number;
  group_name: string;
  status: string;
  original_filename: string;
  total_rows: number;
  valid_rows: number;
  invalid_rows: number;
  review_rows: number;
};

export type MatchRunResponse = {
  job_id: number;
  status: string;
  matched_rows: number;
  review_rows: number;
  unmatched_rows: number;
};

export type ConfirmTargetGroupResponse = {
  job_id: number;
  status: string;
  valid_rows: number;
  invalid_rows: number;
};

export type DiseaseOption = {
  normalized_disease_key: string;
  disease_group_label: string;
  group_type: "disease" | "service";
  diagnosis_code: string | null;
  disease_name_raw: string | null;
};

export type GroupedDiseaseSummary = {
  disease_key: string;
  disease_group_label: string | null;
  total_rows: number;
  matched_rows: number;
  needs_review_rows: number;
  disease_positive_rows: number;
  disease_unknown_rows: number;
};

export type GroupResultRow = {
  id: number;
  row_number: number;
  patient_id: number | null;
  full_name: string | null;
  pid: string | null;
  hn: string | null;
  match_method: string;
  match_status: string;
  selected_disease_key: string | null;
  selected_disease_keys: string[];
  has_disease_history: boolean | null;
  latest_visit_date: string | null;
  visit_count: number | null;
  days_since_latest_visit: number | null;
  years_since_latest_visit: number | null;
  matched_disease_keys: string[];
  matched_disease_labels: string[];
  matched_service_items: string[];
  flags: { code?: string; message?: string }[];
};

export type SearchResultResponse = {
  group_job_id: number;
  filters: Record<string, string[]>;
  results: GroupResultRow[];
};

export type ExportResponse = {
  job_id: number;
  filename: string;
  export_path: string;
  row_count: number;
};

export type PatientSummary = {
  id: number;
  pid: string | null;
  citizen_id: string | null;
  hn: string | null;
  full_name: string | null;
  birth_date: string | null;
};

export type DiagnosisRecord = {
  visit_date: string | null;
  diagnosis_code: string | null;
  disease_name_raw: string | null;
  normalized_disease_key: string | null;
  encounter_type: string | null;
  provider_name: string | null;
};

export type PatientHistoryResponse = {
  patient: PatientSummary;
  history: DiagnosisRecord[];
};
