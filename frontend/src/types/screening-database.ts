export type ImportJobSummary = {
  import_id: string;
  status: string;
  file_name: string;
  file_type: string;
  file_size: number | null;
  detected_rows: number;
  success_rows: number;
  failed_rows: number;
  validation_error_count: number;
  created_at: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_by: string | null;
  source_set_hash: string | null;
  error_summary: string | null;
};

export type ImportSourceFile = {
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
  parse_error_summary?: string | null;
  discovered_at?: string | null;
};

export type ImportJobDetail = ImportJobSummary & {
  source_type: string;
  source_file_hash: string | null;
  source_file_path: string | null;
  source_file_modified_at: string | null;
  parsed_rows: number;
  valid_rows: number;
  invalid_rows: number;
  warning_rows: number;
  merged_rows: number;
  skipped_rows: number;
  duplicate_identifier_count: number;
  source_files: ImportSourceFile[];
};

export type ImportJobListResponse = {
  imports: ImportJobSummary[];
  total: number;
};

export type StageUploadResponse = {
  status: string;
  file_name: string;
  file_type: string;
  file_size: number;
  message: string;
  next_step: string;
  needs_review: boolean;
};
