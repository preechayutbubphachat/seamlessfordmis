export type PatientSummary = {
  id: string;
  pid: string | null;
  citizen_id: string | null;
  hn: string | null;
  full_name: string;
  birth_date: string | null;
};

export type DiagnosisHistoryRow = {
  visit_date: string;
  diagnosis_code: string | null;
  diagnosis_name: string | null;
  normalized_disease_key: string | null;
  department: string | null;
  doctor_name: string | null;
};

export type PatientHistory = {
  patient: PatientSummary;
  history: DiagnosisHistoryRow[];
};

// Phase C / source-history endpoint types ----------------------------------

/** One row from disease_screening_records, returned by source-history endpoint. */
export type ScreeningRecord = {
  record_id: string;
  source_file_name: string | null;
  source_row_no: number | null;
  normalized_person_identifier: string;
  full_name: string | null;
  raw_service_type: string;
  normalized_service_key: string;
  visit_date: string;
};

/** One event row from target_group_history_rows, returned by source-history endpoint. */
export type TgHistoryEvent = {
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
  validation_status: string | null;
  warning_message: string | null;
};

/**
 * Response from GET /api/target-groups/{group_id}/results/{result_id}/source-history.
 * Contains BOTH evidence buckets for one result row so the UI can display them
 * in clearly labelled sections without any de-duplication confusion.
 */
export type ResultSourceHistory = {
  result_id: string;
  normalized_cid: string | null;
  full_name: string | null;
  screening_db_records: ScreeningRecord[];
  target_group_history_events: TgHistoryEvent[];
  history_source_summary:
    | "both_sources"
    | "screening_db_only"
    | "target_group_file_only"
    | "no_history_found";
};
