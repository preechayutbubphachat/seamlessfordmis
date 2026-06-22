export type ResultSummary = {
  group_job_id: string;
  total_target_people: number;
  valid_identifier_people: number;
  invalid_identifier_people: number;
  non_thai_nationality_people: number;
  insufficient_identity_people: number;
  outside_target_scope_people: number;
  review_required_identity_people: number;
  people_with_selected_history: number;
  people_without_selected_history: number;
  never_checked_people: number;
  checked_but_overdue_people: number;
  checked_and_within_threshold_people: number;
  coverage_percent: number;
  coverage_denominator: string;
  coverage_denominator_people: number;
  overdue_threshold_years: number | null;
  selected_service_count: number;
  selected_service_keys: string[];
  generated_at: string | null;
  generated_source_set_hash: string | null;
  normalization_version?: number | null;
  current_normalization_version?: number | null;
  requires_regeneration?: boolean;
};

export type ServiceBreakdown = {
  selected_service_key: string;
  distinct_people_count: number;
  matching_record_count: number;
};

export type GenerateResultsResponse = {
  group_id: string;
  generated_rows: number;
  disease_keys: string[];
  summary: ResultSummary;
  breakdown: ServiceBreakdown[];
};

export type GroupResultRow = {
  result_id: string;
  target_row_id: string | null;
  group_job_id: string;
  patient_id: string | null;
  normalized_cid: string | null;
  matched_identifier: string | null;
  matched_name_basis: string | null;
  full_name: string | null;
  age: number | null;
  raw_age: string | null;
  birth_date: string | null;
  sex: string | null;
  match_status: string;
  match_method: string | null;
  match_confidence: string | null;
  person_link_status: string | null;
  duplicate_reason: string | null;
  review_required: boolean;
  result_category: string;
  result_status: string;
  screening_status: string;
  overdue_threshold_years: number | null;
  has_selected_service: boolean;
  matching_record_count: number;
  matched_service_keys: string[];
  last_visit_date: string | null;
  days_since_last_visit: number | null;
  years_since_last_visit: number | null;
  target_group_history_labels: string | null;
  target_group_history_note: string | null;
  target_group_history_last_visit_date: string | null;
  history_found_in_screening_db: boolean;
  history_found_in_target_group_file: boolean;
  history_source_summary: string;
  last_relevant_source: string | null;
  target_group_nationality: string | null;
  target_group_address: string | null;
  source_file_id: string | null;
  source_file_name: string | null;
  source_sheet_name: string | null;
  source_row_no: number | null;
  source_origin_context: string | null;
  provenance_summary_count: number;
  provenance_details: Array<{
    source_file_id: string | null;
    source_file_name: string | null;
    source_sheet_name?: string | null;
    source_row_no: number | null;
    row_no: number | null;
    match_method: string | null;
    match_status: string | null;
    warning_message: string | null;
    error_message: string | null;
  }>;
  latest_source_file_name: string | null;
  latest_source_sheet_name: string | null;
  latest_source_row_no: number | null;
  screening_db_history_count: number;
  target_group_history_count: number;
  target_group_history_events: Array<{
    source_type: string | null;
    source_file_name: string | null;
    source_sheet_name: string | null;
    source_row_no: number | null;
    raw_service_type: string | null;
    normalized_service_key: string | null;
    visit_date: string | null;
    raw_result: string | null;
    raw_hospital: string | null;
    raw_doctor: string | null;
    raw_note: string | null;
  }>;
  warning_message: string | null;
};

export type GroupResultsResponse = {
  group_id: string;
  summary: ResultSummary;
  breakdown: ServiceBreakdown[];
  results: GroupResultRow[];
  page: number;
  page_size: number;
  total_filtered_rows: number;
  total_pages: number;
};

export type ExportDownload = {
  filename: string;
};
