import type { TargetGroupFile, TargetGroupPreviewRow, ValidationIssue } from "@/types/target-group";

function compact(parts: Array<string | number | null | undefined>) {
  return parts
    .filter((part) => part !== null && part !== undefined && part !== "")
    .map((part) => String(part));
}

export function getTargetGroupFileKey(file: TargetGroupFile) {
  return compact([
    file.file_id,
    file.sha256,
    file.file_name,
    file.file_type,
  ]).join(":");
}

export function getPreviewRowKey(row: TargetGroupPreviewRow) {
  // row_no alone is unsafe because multiple uploaded files can repeat the same
  // display row number inside one logical target group job.
  return compact([
    row.row_id,
    row.source_file_id,
    row.source_file_name,
    row.source_row_no ?? row.row_no,
    row.normalized_cid,
    row.parse_status,
  ]).join(":");
}

export function getValidationIssueKey(issue: ValidationIssue) {
  // Use provenance when possible so repeated row numbers from different files do
  // not collide in React rendering.
  return compact([
    issue.row_id,
    issue.source_file_id,
    issue.source_file_name,
    issue.source_row_no ?? issue.row_no,
    issue.field,
    issue.message,
  ]).join(":");
}

export function getSelectedFileKey(file: File) {
  return compact([file.name, file.size, file.lastModified, file.type]).join(":");
}
