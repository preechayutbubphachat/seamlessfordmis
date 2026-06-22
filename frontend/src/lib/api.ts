import type { PatientHistory, PatientSummary, ResultSourceHistory } from "@/types/patient";
import type { ExportDownload, GenerateResultsResponse, GroupResultsResponse } from "@/types/result";
import type { ImportJobDetail, ImportJobListResponse, StageUploadResponse } from "@/types/screening-database";
import type { SourceCheck, SyncMainDatasetResponse, SystemStatus } from "@/types/system";
import type {
  ConfirmImportResponse,
  DiseaseOption,
  RunMatchResponse,
  TargetGroupDetail,
  TargetGroupFile,
  TargetGroupListItem,
  TargetGroupUploadResponse,
  TargetGroupValidationSummary,
} from "@/types/target-group";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8010";

type ApiErrorPayload = {
  detail?: string;
  message?: string;
  error_type?: string;
  path?: string;
};

export type ApiErrorKind = "network" | "backend" | "timeout";

export class ApiError extends Error {
  status: number;
  detail: string;
  kind: ApiErrorKind;
  payload?: unknown;
  url?: string;

  constructor(
    message: string,
    status = 0,
    kind: ApiErrorKind = "backend",
    options?: { payload?: unknown; url?: string },
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = message;
    this.kind = kind;
    this.payload = options?.payload;
    this.url = options?.url;
  }
}

type GroupResultsQuery = {
  overdueYears?: number;
  page?: number;
  pageSize?: number;
  includeAll?: boolean;
  view?: string;
  query?: string;
  overdueEnabled?: boolean;
  /** Column key to sort by — must match backend SORTABLE_COLUMNS */
  sortCol?: string;
  /** Sort direction; defaults to "asc" when sortCol is set */
  sortDir?: "asc" | "desc";
};

function safeJsonParse(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

// Hard timeout so no request can hang forever (hospital-safe: every fetch must
// resolve as success / empty / error / timeout). Heavy POSTs (generate-results)
// can override via opts.timeoutMs.
const DEFAULT_TIMEOUT_MS = 30_000;

type RequestOptions = { timeoutMs?: number };

async function request<T>(path: string, init?: RequestInit, opts?: RequestOptions): Promise<T> {
  const url = `${API_BASE}${path}`;
  const timeoutMs = opts?.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const startedAt = Date.now();
  // Log path only — query strings may contain typed identifiers (privacy rule).
  console.info("[api] request", { method: init?.method ?? "GET", url: url.split("?")[0], timeoutMs });

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  let response: Response;
  try {
    response = await fetch(url, {
      ...init,
      cache: "no-store",
      signal: controller.signal,
    });
  } catch (error) {
    clearTimeout(timer);
    const durationMs = Date.now() - startedAt;
    // AbortController fired the timeout — surface a distinct timeout error so the
    // UI never sits in an infinite loading state.
    if (controller.signal.aborted) {
      console.warn("[api] timeout", { url: url.split("?")[0], durationMs, timeoutMs });
      throw new ApiError(
        `คำขอใช้เวลานานเกินกำหนด (${Math.round(timeoutMs / 1000)} วินาที) — ตรวจสอบว่า backend และฐานข้อมูลการคัดกรองทำงานปกติ แล้วกดลองใหม่`,
        0,
        "timeout",
        { url },
      );
    }
    // Use warn, not error: Next.js 15 intercepts console.error and re-raises
    // it as an unhandled React error even when it is caught by the caller.
    console.warn("[api] network_error", { url: url.split("?")[0], durationMs, error });
    throw new ApiError("ไม่สามารถเชื่อมต่อกับเซิร์ฟเวอร์ได้ กรุณาตรวจสอบว่า backend กำลังทำงานอยู่", 0, "network", {
      url,
    });
  }
  clearTimeout(timer);

  const rawText = await response.text();
  const payload = rawText ? safeJsonParse(rawText) : null;
  if (!response.ok) {
    const detail =
      (payload as ApiErrorPayload | null)?.detail ||
      (payload as ApiErrorPayload | null)?.message ||
      rawText ||
      `Request failed with status ${response.status}`;
    const normalizedDetail =
      typeof detail === "string" && detail.trim()
        ? detail
        : `เซิร์ฟเวอร์ตอบกลับด้วยสถานะ ${response.status}`;

    // Same rationale: warn so the overlay doesn't appear for handled 4xx/5xx.
    console.warn("[api] backend_error", {
      url: url.split("?")[0],
      status: response.status,
      statusText: response.statusText,
      payload,
      rawText,
      detail: normalizedDetail,
    });
    throw new ApiError(normalizedDetail, response.status, "backend", {
      payload,
      url,
    });
  }

  const data = (payload ?? {}) as T;
  console.info("[api] response", {
    url: url.split("?")[0],
    status: response.status,
    durationMs: Date.now() - startedAt,
  });
  return data;
}

export function getApiErrorMessage(error: unknown, fallback: string) {
  if (error instanceof ApiError) {
    const suffix = error.status ? ` (HTTP ${error.status})` : "";
    return `${error.detail}${suffix}`;
  }
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return fallback;
}

export function getSystemStatus() {
  return request<SystemStatus>("/api/system/status");
}

export function checkSourceUpdate() {
  return request<SourceCheck>("/api/system/check-source-update", { method: "POST" });
}

export function syncDiseaseScreeningDatabase() {
  return request<SyncMainDatasetResponse>(
    "/api/system/sync-disease-screening-database",
    { method: "POST" },
    { timeoutMs: 180_000 },
  );
}

export function syncMainDataset() {
  return syncDiseaseScreeningDatabase();
}

export function listTargetGroups() {
  return request<TargetGroupListItem[]>("/api/target-groups");
}

export function getTargetGroup(groupId: string) {
  return request<TargetGroupDetail>(`/api/target-groups/${groupId}`);
}

export function updateGroupName(groupId: string, groupName: string) {
  return request<TargetGroupDetail>(`/api/target-groups/${groupId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ group_name: groupName }),
  });
}

export function getTargetGroupFiles(groupId: string) {
  return request<TargetGroupFile[]>(`/api/target-groups/${groupId}/files`);
}

export function getTargetGroupValidationSummary(groupId: string) {
  return request<TargetGroupValidationSummary>(`/api/target-groups/${groupId}/validation-summary`);
}

export function getDiseaseOptions() {
  return request<DiseaseOption[]>("/api/target-groups/disease-options");
}

// Heavy import mutation — large Excel/CSV (tens of thousands of rows) can take
// well over the 30s read default. Use a long mutation timeout so the frontend
// does not give up while the backend is still importing.
const IMPORT_TIMEOUT_MS = 180_000;

export function uploadTargetGroupFiles(formData: FormData) {
  return request<TargetGroupUploadResponse>(
    "/api/target-groups/upload-files",
    { method: "POST", body: formData },
    { timeoutMs: IMPORT_TIMEOUT_MS },
  );
}

export function uploadTargetGroup(formData: FormData) {
  return uploadTargetGroupFiles(formData);
}

export function addFilesToGroup(groupId: string, files: File[]) {
  const formData = new FormData();
  for (const file of files) {
    formData.append("files", file);
  }
  return request<TargetGroupDetail>(
    `/api/target-groups/${groupId}/add-files`,
    { method: "POST", body: formData },
    { timeoutMs: IMPORT_TIMEOUT_MS },
  );
}

export function confirmImport(groupId: string) {
  return request<ConfirmImportResponse>(
    `/api/target-groups/${groupId}/confirm-import`,
    { method: "POST" },
    { timeoutMs: 180_000 },
  );
}

export function runMatch(groupId: string) {
  return request<RunMatchResponse>(
    `/api/target-groups/${groupId}/run-match`,
    { method: "POST" },
    { timeoutMs: 180_000 },
  );
}

export function generateResults(groupId: string, diseaseKeys: string[]) {
  // Synchronous matching can run long on large groups — allow more headroom than
  // the default read timeout, but still bound it so the UI can recover.
  return request<GenerateResultsResponse>(
    `/api/target-groups/${groupId}/generate-results`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ disease_keys: diseaseKeys }),
    },
    { timeoutMs: 180_000 },
  );
}

export function getGroupResults(groupId: string, options: GroupResultsQuery = {}) {
  const params = new URLSearchParams();
  params.set("overdue_years", String(options.overdueYears ?? 1));
  params.set("page", String(options.page ?? 1));
  params.set("page_size", String(options.pageSize ?? 100));
  if (options.includeAll) {
    params.set("include_all", "true");
  }
  if (options.view && options.view !== "all") {
    params.set("view", options.view);
  }
  if (options.query?.trim()) {
    params.set("query", options.query.trim());
  }
  if (options.overdueEnabled) {
    params.set("overdue_enabled", "true");
  }
  if (options.sortCol) {
    params.set("sort_col", options.sortCol);
    params.set("sort_dir", options.sortDir ?? "asc");
  }
  return request<GroupResultsResponse>(`/api/target-groups/${groupId}/results?${params.toString()}`);
}

function buildExportUrl(groupId: string, format: "xlsx" | "csv", selectedServiceKeys: string[]) {
  const params = new URLSearchParams({ format });
  for (const key of selectedServiceKeys) {
    params.append("selected_service_keys", key);
  }
  return `${API_BASE}/api/target-groups/${groupId}/export?${params.toString()}`;
}

export async function exportGroupResults(
  groupId: string,
  format: "xlsx" | "csv",
  selectedServiceKeys: string[],
): Promise<ExportDownload> {
  const url = buildExportUrl(groupId, format, selectedServiceKeys);
  console.info("[api] export.request", { url });

  let response: Response;
  try {
    response = await fetch(url, { method: "GET", cache: "no-store" });
  } catch (error) {
    console.error("[api] export.network_error", { url, error });
    throw new ApiError("ไม่สามารถเชื่อมต่อกับเซิร์ฟเวอร์เพื่อดาวน์โหลดรายงานได้", 0, "network", { url });
  }

  if (!response.ok) {
    const rawText = await response.text();
    const payload = rawText ? safeJsonParse(rawText) : null;
    const detail =
      (payload as ApiErrorPayload | null)?.detail ||
      (payload as ApiErrorPayload | null)?.message ||
      rawText ||
      `Request failed with status ${response.status}`;
    throw new ApiError(detail, response.status, "backend", { payload, url });
  }

  const blob = await response.blob();
  const contentDisposition = response.headers.get("content-disposition") ?? "";
  const match = /filename=\"?([^\"]+)\"?/i.exec(contentDisposition);
  const filename = match?.[1] ?? `target-group-export.${format}`;
  const objectUrl = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(objectUrl);
  console.info("[api] export.response", { url, status: response.status, filename });
  return { filename };
}

export function searchPatients(query: string) {
  return request<PatientSummary[]>(`/api/patients/search?query=${encodeURIComponent(query)}`);
}

export function getPatientHistory(patientId: string) {
  return request<PatientHistory>(`/api/patients/${patientId}/history`);
}

// Fetch both evidence sources for a single result row.
// GET /api/target-groups/:groupId/results/:resultId/source-history
// Returns screening_db_records + target_group_history_events in separate buckets.
export function getResultSourceHistory(
  groupId: string,
  resultId: string,
  selectedServiceKeys?: string[],
): Promise<ResultSourceHistory> {
  const params = new URLSearchParams();
  if (selectedServiceKeys?.length) {
    for (const key of selectedServiceKeys) {
      params.append("service_keys", key);
    }
  }
  const paramsStr = params.toString();
  const qs = paramsStr.length > 0 ? ("?" + paramsStr) : "";
  return request<ResultSourceHistory>(
    "/api/target-groups/" + groupId + "/results/" + resultId + "/source-history" + qs,
  );
}

// ---------------------------------------------------------------------------
// Screening database — import history + file staging
// ---------------------------------------------------------------------------

export function listScreeningImports(limit = 20, offset = 0): Promise<ImportJobListResponse> {
  return request<ImportJobListResponse>(
    `/api/screening-database/imports?limit=${limit}&offset=${offset}`,
  );
}

export function getScreeningImportDetail(importId: string): Promise<ImportJobDetail> {
  return request<ImportJobDetail>(`/api/screening-database/imports/${importId}`);
}

function buildScreeningImportReportUrl(importId: string) {
  return `${API_BASE}/api/screening-database/imports/${importId}/report`;
}

export async function downloadScreeningImportReport(importId: string): Promise<ExportDownload> {
  const url = buildScreeningImportReportUrl(importId);
  let response: Response;
  try {
    response = await fetch(url, { method: "GET", cache: "no-store" });
  } catch (error) {
    console.error("[api] screening_import_report.network_error", { url, error });
    throw new ApiError("ไม่สามารถเชื่อมต่อกับเซิร์ฟเวอร์เพื่อดาวน์โหลดรายงานได้", 0, "network", { url });
  }
  if (!response.ok) {
    const rawText = await response.text();
    const payload = rawText ? safeJsonParse(rawText) : null;
    const detail =
      (payload as ApiErrorPayload | null)?.detail ||
      (payload as ApiErrorPayload | null)?.message ||
      rawText ||
      `Request failed with status ${response.status}`;
    throw new ApiError(detail, response.status, "backend", { payload, url });
  }

  const blob = await response.blob();
  const contentDisposition = response.headers.get("content-disposition") ?? "";
  const match = /filename=\"?([^\"]+)\"?/i.exec(contentDisposition);
  const filename = match?.[1] ?? `screening-import-${importId.slice(0, 8)}-summary.csv`;
  const objectUrl = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(objectUrl);
  return { filename };
}

export function stageUploadScreeningFile(formData: FormData): Promise<StageUploadResponse> {
  return request<StageUploadResponse>(
    "/api/screening-database/stage-upload",
    { method: "POST", body: formData },
    { timeoutMs: 180_000 },
  );
}
