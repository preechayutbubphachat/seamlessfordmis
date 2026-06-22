"use client";

import { useRef, useState } from "react";

import { addFilesToGroup, ApiError } from "@/lib/api";
import { formatNumber } from "@/lib/format";
import type { TargetGroupDetail, TargetGroupFile } from "@/types/target-group";

// ─────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────

const ACCEPTED_EXTS = [".xlsx", ".xls", ".csv", ".pdf"];
const ACCEPT_ATTR = ACCEPTED_EXTS.join(",");

function formatBytes(bytes: number): string {
  if (bytes < 1024) return String(bytes) + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / (1024 * 1024)).toFixed(1) + " MB";
}

function fileExt(name: string): string {
  return name.slice(name.lastIndexOf(".")).toLowerCase();
}

function parseStatusLabel(status: string | null): { text: string; tone: string } {
  switch (status) {
    case "parsed": return { text: "นำเข้าแล้ว", tone: "ready" };
    case "failed": return { text: "นำเข้าไม่สำเร็จ", tone: "warning" };
    case "pending": return { text: "รอดำเนินการ", tone: "muted" };
    default: return { text: status ?? "-", tone: "muted" };
  }
}

// ─────────────────────────────────────────────────────────
// Sub-components
// ─────────────────────────────────────────────────────────

function ExistingFileRow({ file }: { file: TargetGroupFile }) {
  const { text, tone } = parseStatusLabel(file.parse_status);
  return (
    <div className="file-row">
      <div className="file-row-name">
        <span className="file-ext-badge">{fileExt(file.file_name).replace(".", "").toUpperCase()}</span>
        <span className="file-row-filename">{file.file_name}</span>
      </div>
      <div className="file-row-meta">
        <span className={"status-chip " + tone}>{text}</span>
        <span className="status-chip muted">{formatNumber(file.row_count ?? 0) + " แถว"}</span>
        {file.size_bytes ? (
          <span className="status-chip muted">{formatBytes(file.size_bytes)}</span>
        ) : null}
        {file.parse_error_summary ? (
          <span className="status-chip warning" title={file.parse_error_summary}>{"!"}</span>
        ) : null}
      </div>
    </div>
  );
}

function SelectedFileRow({
  file,
  onRemove,
}: {
  file: File;
  onRemove: () => void;
}) {
  return (
    <div className="file-row">
      <div className="file-row-name">
        <span className="file-ext-badge">{fileExt(file.name).replace(".", "").toUpperCase()}</span>
        <span className="file-row-filename">{file.name}</span>
      </div>
      <div className="file-row-meta">
        <span className="status-chip muted">{formatBytes(file.size)}</span>
        <button
          type="button"
          className="ghost-button compact-button"
          onClick={onRemove}
          aria-label={"ลบ " + file.name}
        >
          {"✕"}
        </button>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────
// Main component
// ─────────────────────────────────────────────────────────

export function FileManagementPanel({
  group,
  onFilesAdded,
}: {
  group: TargetGroupDetail;
  onFilesAdded: (updated: TargetGroupDetail) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);

  function handleFileInputChange(e: React.ChangeEvent<HTMLInputElement>) {
    const picked = Array.from(e.target.files ?? []);
    appendFiles(picked);
    // Reset input so the same file can be re-selected after removal
    e.target.value = "";
  }

  function appendFiles(incoming: File[]) {
    setUploadError(null);
    setSuccessMessage(null);
    const valid = incoming.filter((f) =>
      ACCEPTED_EXTS.some((ext) => f.name.toLowerCase().endsWith(ext)),
    );
    const invalid = incoming.filter(
      (f) => !ACCEPTED_EXTS.some((ext) => f.name.toLowerCase().endsWith(ext)),
    );
    if (invalid.length) {
      setUploadError(
        "ไฟล์ต่อไปนี้ไม่รองรับ: " +
          invalid.map((f) => f.name).join(", ") +
          " (รองรับเฉพาะ .xlsx, .xls, .csv, .pdf)",
      );
    }
    if (valid.length) {
      setSelectedFiles((prev) => {
        const existingNames = new Set(prev.map((f) => f.name));
        return [...prev, ...valid.filter((f) => !existingNames.has(f.name))];
      });
    }
  }

  function removeSelected(index: number) {
    setSelectedFiles((prev) => prev.filter((_, i) => i !== index));
    setUploadError(null);
  }

  function handleDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragOver(false);
    appendFiles(Array.from(e.dataTransfer.files));
  }

  async function handleUpload() {
    if (!selectedFiles.length) return;
    setUploading(true);
    setUploadError(null);
    setSuccessMessage(null);
    try {
      const updated = await addFilesToGroup(group.group_id, selectedFiles);
      setSelectedFiles([]);
      const addedCount = updated.source_file_count - group.source_file_count;
      setSuccessMessage(
        "เพิ่มไฟล์สำเร็จ " +
          formatNumber(addedCount > 0 ? addedCount : selectedFiles.length) +
          " ไฟล์ — ระบบได้รีเซ็ตสถานะการจับคู่แล้ว กรุณาสร้างผลลัพธ์ใหม่",
      );
      onFilesAdded(updated);
    } catch (err) {
      setUploadError(err instanceof ApiError ? err.detail : "อัปโหลดไฟล์ไม่สำเร็จ กรุณาลองใหม่อีกครั้ง");
    } finally {
      setUploading(false);
    }
  }

  const existingFiles = group.uploaded_files;
  const canUpload = selectedFiles.length > 0 && !uploading;

  return (
    <section className="panel file-management-panel" aria-label="จัดการไฟล์ข้อมูลกลุ่มเป้าหมาย">
      <p className="eyebrow">{"ขั้นที่ 2 — ไฟล์ข้อมูล"}</p>
      <h3>{"จัดการไฟล์ข้อมูลกลุ่มเป้าหมาย"}</h3>
      <p className="summary-copy">
        {"สามารถเพิ่มไฟล์ใหม่เข้ากลุ่มนี้ได้โดยไม่ต้องสร้างกลุ่มใหม่ หลังจากเพิ่มไฟล์ระบบจะรีเซ็ตสถานะการจับคู่และต้องสร้างผลลัพธ์ใหม่"}
      </p>

      {/* Existing files */}
      <div className="section-block">
        <p className="summary-copy">
          {"ไฟล์ที่มีอยู่ในกลุ่มนี้ (" + formatNumber(existingFiles.length) + " ไฟล์)"}
        </p>
        {existingFiles.length === 0 ? (
          <p className="summary-copy">{"ยังไม่มีไฟล์"}</p>
        ) : (
          <div className="file-list">
            {existingFiles.map((file) => (
              <ExistingFileRow key={file.file_name + (file.sha256 ?? "")} file={file} />
            ))}
          </div>
        )}
      </div>

      {/* Drop zone */}
      <div
        className={["drop-zone", dragOver ? "drop-zone--over" : ""].filter(Boolean).join(" ")}
        role="button"
        tabIndex={0}
        aria-label="คลิกหรือลากไฟล์มาวางที่นี่เพื่อเพิ่มไฟล์"
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") inputRef.current?.click(); }}
      >
        <p className="drop-zone-icon" aria-hidden="true">{"📂"}</p>
        <p className="drop-zone-label">{"คลิกหรือลากไฟล์มาวางที่นี่"}</p>
        <p className="drop-zone-hint">{"รองรับ .xlsx, .xls, .csv, .pdf"}</p>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={ACCEPT_ATTR}
          className="sr-only"
          onChange={handleFileInputChange}
          disabled={uploading}
        />
      </div>

      {/* Selected files pending upload */}
      {selectedFiles.length > 0 ? (
        <div className="section-block">
          <p className="summary-copy">
            {"ไฟล์ที่เลือก (" + formatNumber(selectedFiles.length) + " ไฟล์) — ยังไม่ได้อัปโหลด"}
          </p>
          <div className="file-list">
            {selectedFiles.map((file, index) => (
              <SelectedFileRow
                key={file.name + String(index)}
                file={file}
                onRemove={() => removeSelected(index)}
              />
            ))}
          </div>
        </div>
      ) : null}

      {/* Upload button */}
      <div className="button-row section-block">
        <button
          type="button"
          className="primary-button"
          disabled={!canUpload}
          onClick={() => void handleUpload()}
        >
          {uploading
            ? "กำลังอัปโหลด..."
            : "เพิ่ม " + formatNumber(selectedFiles.length) + " ไฟล์เข้ากลุ่มนี้"}
        </button>
        {selectedFiles.length > 0 ? (
          <button
            type="button"
            className="ghost-button"
            disabled={uploading}
            onClick={() => { setSelectedFiles([]); setUploadError(null); }}
          >
            {"ยกเลิกทั้งหมด"}
          </button>
        ) : null}
      </div>

      {uploadError ? (
        <p className="feedback-line is-error" role="alert">{uploadError}</p>
      ) : null}
      {successMessage ? (
        <p className="feedback-line is-success" role="status">{successMessage}</p>
      ) : null}
    </section>
  );
}
