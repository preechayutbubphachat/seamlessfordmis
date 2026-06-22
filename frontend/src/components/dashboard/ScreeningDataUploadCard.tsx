"use client";

import { useRef, useState } from "react";

import { ApiError, stageUploadScreeningFile } from "@/lib/api";
import type { StageUploadResponse } from "@/types/screening-database";

const ALLOWED_EXTENSIONS = [".xlsx", ".xls", ".csv", ".pdf"];
const MAX_SIZE_BYTES = 200 * 1024 * 1024; // 200 MB

type UploadState = "idle" | "validating" | "uploading" | "staged" | "staged_pdf" | "error";

type PendingFile = {
  file: File;
  validationError: string | null;
};

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function validateFile(file: File): string | null {
  const ext = "." + file.name.split(".").pop()?.toLowerCase();
  if (!ALLOWED_EXTENSIONS.includes(ext)) {
    return `ประเภทไฟล์ไม่รองรับ (${ext}) — รองรับ: ${ALLOWED_EXTENSIONS.join(", ")}`;
  }
  if (file.size === 0) return "ไฟล์ว่างเปล่า";
  if (file.size > MAX_SIZE_BYTES) {
    return `ไฟล์ใหญ่เกิน 200 MB (${formatFileSize(file.size)})`;
  }
  return null;
}

export function ScreeningDataUploadCard({ onUploadSuccess }: { onUploadSuccess?: () => void }) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [pending, setPending] = useState<PendingFile[]>([]);
  const [uploadState, setUploadState] = useState<UploadState>("idle");
  const [uploadResult, setUploadResult] = useState<StageUploadResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  function reset() {
    setPending([]);
    setUploadState("idle");
    setUploadResult(null);
    setErrorMessage(null);
  }

  function addFiles(files: FileList | File[]) {
    const arr = Array.from(files);
    const validated: PendingFile[] = arr.map((f) => ({
      file: f,
      validationError: validateFile(f),
    }));
    setPending((prev) => [...prev, ...validated]);
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragging(false);
    if (e.dataTransfer.files.length) addFiles(e.dataTransfer.files);
  }

  function handleDragOver(e: React.DragEvent) {
    e.preventDefault();
    setDragging(true);
  }

  function handleDragLeave() {
    setDragging(false);
  }

  function handleInputChange(e: React.ChangeEvent<HTMLInputElement>) {
    if (e.target.files?.length) addFiles(e.target.files);
    // reset input so same file can be selected again if needed
    e.target.value = "";
  }

  function removePending(index: number) {
    setPending((prev) => prev.filter((_, i) => i !== index));
  }

  const hasValidationErrors = pending.some((p) => p.validationError !== null);
  const canUpload = pending.length > 0 && !hasValidationErrors;

  async function handleUpload() {
    if (!canUpload) return;

    // Upload one file at a time (current backend accepts single file per request)
    const firstValid = pending[0];
    if (!firstValid) return;

    setUploadState("uploading");
    setErrorMessage(null);
    setUploadResult(null);

    try {
      const formData = new FormData();
      formData.append("file", firstValid.file);
      const result = await stageUploadScreeningFile(formData);
      setUploadResult(result);
      setUploadState(result.needs_review ? "staged_pdf" : "staged");
      setPending([]);
      onUploadSuccess?.();
    } catch (err) {
      setUploadState("error");
      if (err instanceof ApiError) {
        setErrorMessage(err.detail);
      } else {
        setErrorMessage("เกิดข้อผิดพลาดขณะอัปโหลด — กรุณาลองใหม่");
      }
    }
  }

  return (
    <section className="panel db-middle-card">
      <div>
        <p className="eyebrow">{"อัปโหลดข้อมูล"}</p>
        <h3>{"อัปโหลดข้อมูลการคัดกรอง"}</h3>
        <p className="summary-copy" style={{ marginTop: "4px" }}>
          {"รองรับการนำเข้าข้อมูลจากหลายรูปแบบไฟล์"}
        </p>
      </div>

      {/* Drop zone */}
      {uploadState === "idle" || uploadState === "validating" ? (
        <div
          className={`db-dropzone${dragging ? " db-dropzone--active" : ""}`}
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onClick={() => inputRef.current?.click()}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => e.key === "Enter" && inputRef.current?.click()}
          aria-label="คลิกหรือลากไฟล์มาวางที่นี่"
        >
          <input
            ref={inputRef}
            type="file"
            accept=".xlsx,.xls,.csv,.pdf"
            multiple
            style={{ display: "none" }}
            onChange={handleInputChange}
          />
          <div className="db-dropzone-icon">
            <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 16.5V9.75m0 0-3 3m3-3 3 3M6.75 19.5a4.5 4.5 0 0 1-1.41-8.775 5.25 5.25 0 0 1 10.233-2.33 3 3 0 0 1 3.758 3.848A3.752 3.752 0 0 1 18 19.5H6.75Z" />
            </svg>
          </div>
          <p className="db-dropzone-main">{"ลากไฟล์มาวางที่นี่"}</p>
          <p className="db-dropzone-or">{"หรือ"}</p>
          <button
            type="button"
            className="secondary-button compact-button"
            onClick={(e) => {
              e.stopPropagation();
              inputRef.current?.click();
            }}
          >
            {"เลือกไฟล์จากคอมพิวเตอร์"}
          </button>
          <p className="db-dropzone-hint">
            {"รองรับไฟล์: Excel (.xlsx, .xls), CSV, PDF · ขนาดสูงสุด 200 MB"}
          </p>
        </div>
      ) : null}

      {/* Pending file list */}
      {pending.length > 0 && (
        <div className="subtle-box" style={{ marginTop: "12px" }}>
          <p className="summary-copy" style={{ marginBottom: "8px" }}>
            {"ไฟล์ที่เลือก"}
          </p>
          {pending.map((p, i) => (
            <div key={`${p.file.name}-${i}`} className="db-pending-file">
              <div className="db-pending-file-info">
                <span className="db-pending-file-name">{p.file.name}</span>
                <span className="db-pending-file-size">{formatFileSize(p.file.size)}</span>
              </div>
              {p.validationError ? (
                <span className="db-pending-file-error">{p.validationError}</span>
              ) : (
                <span className="db-pending-file-ok">{"✓ พร้อมอัปโหลด"}</span>
              )}
              <button
                type="button"
                className="db-remove-btn"
                onClick={() => removePending(i)}
                aria-label={`ลบไฟล์ ${p.file.name}`}
              >
                {"✕"}
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Upload button */}
      {pending.length > 0 && uploadState !== "uploading" && (
        <div className="button-row" style={{ marginTop: "12px" }}>
          <button
            type="button"
            className="primary-button compact-button"
            disabled={!canUpload}
            onClick={handleUpload}
          >
            {`อัปโหลด ${pending.length} ไฟล์`}
          </button>
          <button
            type="button"
            className="secondary-button compact-button"
            onClick={reset}
          >
            {"ยกเลิก"}
          </button>
        </div>
      )}

      {/* Uploading state */}
      {uploadState === "uploading" && (
        <div className="loading-state" style={{ marginTop: "14px" }}>
          <span className="loading-spinner" />
          <span>{"กำลังอัปโหลดไฟล์เข้าระบบ...  (ห้ามปิดหน้า)"}</span>
        </div>
      )}

      {/* Success state */}
      {(uploadState === "staged" || uploadState === "staged_pdf") && uploadResult && (
        <div
          className={`db-upload-result ${uploadResult.needs_review ? "db-upload-result--warning" : "db-upload-result--success"}`}
          style={{ marginTop: "14px" }}
        >
          <p className="db-upload-result-title">
            {uploadResult.needs_review ? "⚠️ อัปโหลดแล้ว — ต้องตรวจสอบก่อน" : "✓ อัปโหลดสำเร็จ — รออยู่ในคิว"}
          </p>
          <p style={{ marginTop: "6px", fontSize: "0.88rem" }}>{uploadResult.message}</p>
          <p
            className="db-upload-result-next"
            style={{ marginTop: "8px" }}
          >
            <strong>{"ขั้นตอนต่อไป:"}</strong> {uploadResult.next_step}
          </p>
          <button
            type="button"
            className="secondary-button compact-button"
            onClick={reset}
            style={{ marginTop: "10px" }}
          >
            {"อัปโหลดไฟล์อื่น"}
          </button>
        </div>
      )}

      {/* Error state */}
      {uploadState === "error" && errorMessage && (
        <div className="db-upload-result db-upload-result--error" style={{ marginTop: "14px" }}>
          <p className="db-upload-result-title">{"✕ อัปโหลดไม่สำเร็จ"}</p>
          <p style={{ marginTop: "6px", fontSize: "0.88rem" }}>{errorMessage}</p>
          <button
            type="button"
            className="secondary-button compact-button"
            onClick={reset}
            style={{ marginTop: "10px" }}
          >
            {"ลองใหม่"}
          </button>
        </div>
      )}

      {/* Info strip */}
      <div className="db-info-strip" style={{ marginTop: "14px" }}>
        <span className="db-info-icon">{"ℹ"}</span>
        <span>
          {"แนะนำ: ตรวจสอบรูปแบบไฟล์และความถูกต้องของข้อมูลก่อนนำเข้า "}
          <span className="db-info-note">{"(PDF ยังอยู่ในโหมด staged — ต้องตรวจสอบก่อน commit)"}</span>
        </span>
      </div>
    </section>
  );
}
