export type ValidationIssue = {
  row_id?: string | null;
  row_no: number;
  source_file_id?: string | null;
  source_file_name?: string | null;
  source_row_no?: number | null;
  field: string;
  message: string;
};

export type TargetGroupPreviewRow = {
  row_id?: string | null;
  row_no: number;
  source_file_id?: string | null;
  source_file_name?: string | null;
  source_row_no?: number | null;
  normalized_cid?: string | null;
  parse_status?: string | null;
  values: Record<string, string | number | null>;
};

export type MatchSummary = {
  matched: number;
  not_found: number;
  ambiguous: number;
  needs_review: number;
  pending: number;
};

export type DiseaseOption = {
  key: string;
  label: string;
  icd10_code: string | null;
  raw_name: string | null;
};

export type TargetGroupFile = {
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
};

export type TargetGroupSheet = {
  sheet_id: string;
  source_file_id?: string | null;
  sheet_name: string;
  sheet_index: number;
  sheet_type: string;
  row_count: number;
  column_names: string[];
  classification_confidence?: number | null;
  notes?: string | null;
};

export type TargetGroupImportSummary = {
  total_uploaded_files: number;
  total_rows: number;
  parsed_rows: number;
  valid_cid_rows: number;
  invalid_cid_rows: number;
  missing_cid_rows: number;
  duplicate_cid_rows: number;
  warning_rows: number;
  failed_rows: number;
};

export type TargetGroupUploadResponse = {
  group_id: string;
  group_name: string;
  parse_status: string;
  source_file_count: number;
  total_rows: number;
  import_summary?: TargetGroupImportSummary;
  uploaded_files: TargetGroupFile[];
  sheets: TargetGroupSheet[];
  preview_rows: TargetGroupPreviewRow[];
  validation_issues: ValidationIssue[];
  uploaded_at: string;
};

export type ConfirmImportResponse = {
  group_id: string;
  parse_status: string;
  match_status: string;
};

export type RunMatchResponse = {
  group_id: string;
  match_status: string;
  matched_rows: number;
  not_found_rows: number;
  ambiguous_rows: number;
  needs_review_rows: number;
};

export type TargetGroupListItem = {
  group_id: string;
  group_name: string;
  source_file_name: string;
  source_file_type: string;
  source_file_count: number;
  parse_status: string;
  match_status: string;
  total_rows: number;
  invalid_rows: number;
  import_summary?: TargetGroupImportSummary;
  match_summary: MatchSummary;
  uploaded_at: string;
};

export type TargetGroupDetail = {
  group_id: string;
  group_name: string;
  source_file_name: string;
  source_file_type: string;
  source_file_hash: string;
  source_set_hash: string | null;
  source_file_count: number;
  parse_status: string;
  match_status: string;
  total_rows: number;
  invalid_rows: number;
  import_summary?: TargetGroupImportSummary;
  match_summary: MatchSummary;
  uploaded_files: TargetGroupFile[];
  sheets: TargetGroupSheet[];
  preview_rows: TargetGroupPreviewRow[];
  validation_issues: ValidationIssue[];
  uploaded_at: string;
};

export type TargetGroupValidationSummary = {
  group_id: string;
  total_rows: number;
  invalid_rows: number;
  missing_cid_rows: number;
  duplicate_cid_rows: number;
  review_required_rows: number;
  validation_issues: ValidationIssue[];
};
