import {
  DatasetStatus,
  ConfirmTargetGroupResponse,
  DiseaseOption,
  ExportResponse,
  GroupedDiseaseSummary,
  MatchRunResponse,
  PatientHistoryResponse,
  SearchResultResponse,
  SyncResponse,
  TargetGroupJob,
  TargetGroupUploadResponse
} from "@/types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000/api/v1";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    cache: "no-store"
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed with status ${response.status}`);
  }

  return (await response.json()) as T;
}

export function getSystemStatus() {
  return request<DatasetStatus>("/system/status");
}

export function syncMainDataset() {
  return request<SyncResponse>("/source/sync", {
    method: "POST"
  });
}

export function getDiseaseMappings() {
  return request<DiseaseOption[]>("/disease-mappings");
}

export function getTargetGroup(jobId: number | string) {
  return request<TargetGroupJob>(`/target-groups/${jobId}`);
}

export function getGroupedDiseaseSummary(jobId: number | string) {
  return request<GroupedDiseaseSummary[]>(`/target-groups/${jobId}/summary`);
}

export function getGroupResults(jobId: number | string, diseaseKeys: string[]) {
  return request<SearchResultResponse>(`/target-groups/${jobId}/results`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ disease_keys: diseaseKeys })
  });
}

export function confirmTargetGroup(jobId: number | string) {
  return request<ConfirmTargetGroupResponse>(`/target-groups/${jobId}/confirm`, {
    method: "POST"
  });
}

export function runMatching(jobId: number | string) {
  return request<MatchRunResponse>(`/target-groups/${jobId}/match`, {
    method: "POST"
  });
}

export function exportResults(jobId: number | string) {
  return request<ExportResponse>(`/target-groups/${jobId}/export`, {
    method: "POST"
  });
}

export function uploadTargetGroup(formData: FormData) {
  return request<TargetGroupUploadResponse>("/target-groups/upload", {
    method: "POST",
    body: formData
  });
}

export function getPatientHistory(patientId: number | string) {
  return request<PatientHistoryResponse>(`/patients/${patientId}/history`);
}
