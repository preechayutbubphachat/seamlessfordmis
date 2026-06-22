export type FileFingerprint = {
  filename: string;
  path: string;
  sha256: string;
  size_bytes: number;
  modified_at: string;
};

export type SourceFileStatus = {
  file_id: string | null;
  file_name: string;
  file_path: string | null;
  file_type: string;
  sha256: string;
  size_bytes: number;
  modified_at: string | null;
  parse_status: string | null;
  row_count: number | null;
  warning_count: number | null;
  error_message: string | null;
};

export type SystemStatus = {
  dataset_ready: boolean;
  source_file_exists: boolean;
  source_file_changed: boolean;
  source_file_count: number;
  source_set_hash: string | null;
  latest_import_job_id: string | null;
  import_status: string | null;
  row_counts: Record<string, number>;
  fingerprint: FileFingerprint | null;
  source_files: SourceFileStatus[];
};

export type SourceCheck = {
  changed: boolean;
  reason: string;
  source_file_count: number;
  source_set_hash: string | null;
  fingerprint: FileFingerprint | null;
  files: SourceFileStatus[];
  previous_import: Record<string, unknown> | null;
};

export type SyncMainDatasetResponse = {
  import_job_id: string;
  status: string;
  source_file_count: number;
  source_set_hash: string | null;
  total_rows: number;
  success_rows: number;
  failed_rows: number;
  started_at: string | null;
  finished_at: string | null;
  validation_issues: { row_no: number; field: string; message: string }[];
};
