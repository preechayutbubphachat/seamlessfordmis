"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState, useTransition } from "react";
import { useRouter } from "next/navigation";

import { JobProgressCard } from "@/components/common/JobProgressCard";
import { StageProgress } from "@/components/common/StageProgress";
import { useElapsedSeconds } from "@/components/common/useElapsedSeconds";
import { ApiError, generateResults, getApiErrorMessage, getDiseaseOptions, listTargetGroups, uploadTargetGroupFiles } from "@/lib/api";
import { formatDate, formatNumber } from "@/lib/format";
import type {
  DiseaseOption,
  TargetGroupImportSummary,
  TargetGroupListItem,
  TargetGroupUploadResponse,
} from "@/types/target-group";
import { getSelectedFileKey, getTargetGroupFileKey, getValidationIssueKey } from "./keys";
import { TargetGroupPreviewTable } from "./TargetGroupPreviewTable";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const ACCEPTED_TYPES = ".xlsx,.xls,.csv,.pdf";

const EMPTY_IMPORT_SUMMARY: TargetGroupImportSummary = {
  total_uploaded_files: 0,
  total_rows: 0,
  parsed_rows: 0,
  valid_cid_rows: 0,
  invalid_cid_rows: 0,
  missing_cid_rows: 0,
  duplicate_cid_rows: 0,
  warning_rows: 0,
  failed_rows: 0,
};

const STEPS = [
  {
    id: "name",
    label: "ตั้งชื่อกลุ่ม",
    short: "ตั้งชื่อ",
    hint: "ใส่ชื่อกลุ่มที่อ่านง่าย เช่น “คัดกรองมะเร็งปากมดลูก ไตรมาส 2/2569”",
  },
  {
    id: "upload",
    label: "อัปโหลดไฟล์ต้นทาง",
    short: "อัปโหลด",
    hint: "Excel, CSV หรือ PDF ทุกไฟล์จะถูกเก็บ provenance ไว้ตรวจสอบย้อนหลังได้",
  },
  {
    id: "preview",
    label: "ตรวจตัวอย่าง",
    short: "ตรวจตัวอย่าง",
    hint: "ดู preview รายการแถวที่มี warning และ CID ที่ใช้งานได้ ก่อนเลือกโรค/บริการ",
  },
  {
    id: "generate",
    label: "สร้างผลลัพธ์",
    short: "จับคู่",
    hint: "เลือกโรค/บริการที่ต้องการจับคู่กับฐานข้อมูลการตรวจโรค ระบบจะไม่จับคู่กำกวมโดยอัตโนมัติ",
  },
  {
    id: "review",
    label: "ตรวจสอบและส่งออก",
    short: "ส่งออก",
    hint: "เปิดหน้าผลลัพธ์เพื่อ filter / export Excel ส่งให้ทีมปฏิบัติงาน",
  },
] as const;

type StepId = (typeof STEPS)[number]["id"];

// Stage labels for the "สร้างผลลัพธ์" lifecycle. Stage-based UI only — these
// describe the request lifecycle, not real server-side progress.
const GENERATE_STAGES = [
  "ส่งคำขอสร้างผลลัพธ์",
  "จับคู่ตัวระบุ (exact CID)",
  "ตรวจประวัติจากฐานข้อมูลการคัดกรอง",
  "ตรวจประวัติฝั่งกลุ่มเป้าหมาย",
  "รวม provenance",
  "สร้างตารางผลลัพธ์ (1 คน = 1 แถว)",
  "โหลดผลลัพธ์ล่าสุด",
];

function debugLog(event: string, detail: Record<string, unknown>) {
  // Desktop/dev diagnostics — never log CID, names, or uploaded row content.
  console.info(`[tg-detail] ${event}`, detail);
}

// ---------------------------------------------------------------------------
// Step indicator circle
// ---------------------------------------------------------------------------

function StepIndicator({ status, number }: { status: "pending" | "active" | "done"; number: number }) {
  return (
    <div className={`step-indicator step-indicator--${status}`} aria-hidden="true">
      {status === "done" ? "✓" : number}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Horizontal stepper header
// ---------------------------------------------------------------------------

function HorizontalStepper({
  currentIdx,
  maxReached,
  onJump,
}: {
  currentIdx: number;
  maxReached: number;
  onJump: (idx: number) => void;
}) {
  return (
    <div className="hstepper-wrap">
      <ol className="hstepper">
        {STEPS.map((step, idx) => {
          let status: "pending" | "active" | "done" = "pending";
          if (idx < currentIdx) status = "done";
          if (idx === currentIdx) status = "active";
          const clickable = idx <= maxReached;

          return (
            <li key={step.id} className={`hstepper-item hstepper-item--${status}`}>
              <button
                type="button"
                className="hstepper-button"
                onClick={() => clickable && onJump(idx)}
                disabled={!clickable}
                aria-current={idx === currentIdx ? "step" : undefined}
              >
                <StepIndicator status={status} number={idx + 1} />
                <div className="hstepper-label">
                  <p className="eyebrow">{"ขั้นที่ "}{idx + 1}</p>
                  <p className="hstepper-text">{step.short}</p>
                </div>
              </button>
              {idx < STEPS.length - 1 ? <div className="hstepper-connector" /> : null}
            </li>
          );
        })}
      </ol>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Service selector chip (step 4)
// ---------------------------------------------------------------------------

function ServiceChip({
  option,
  checked,
  onChange,
}: {
  option: DiseaseOption;
  checked: boolean;
  onChange: () => void;
}) {
  return (
    <label className={`service-chip${checked ? " is-active" : ""}`}>
      <input type="checkbox" checked={checked} onChange={onChange} />
      <span>{option.label}</span>
    </label>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function TargetGroupUploadForm({ recentGroups }: { recentGroups: TargetGroupListItem[] }) {
  const router = useRouter();

  // — Wizard state —
  const [pageIdx, setPageIdx] = useState(0);

  // Step 1 — name
  const [groupName, setGroupName] = useState("");

  // Step 2 — upload
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [uploadStatus, setUploadStatus] = useState<"idle" | "processing" | "success" | "failed">("idle");
  const [uploadMessage, setUploadMessage] = useState<string | null>(null);
  // Set when a timeout/duplicate is reconciled to an existing group — lets the
  // user jump to it instead of retrying (which would create a duplicate job).
  const [recoveredGroupId, setRecoveredGroupId] = useState<string | null>(null);
  const [preview, setPreview] = useState<TargetGroupUploadResponse | null>(null);
  const [isUploading, startUpload] = useTransition();

  // Step 4 — generate
  const [diseaseOptions, setDiseaseOptions] = useState<DiseaseOption[]>([]);
  const [optionsStatus, setOptionsStatus] = useState<"idle" | "loading" | "success" | "error">("idle");
  const [optionsError, setOptionsError] = useState<string | null>(null);
  const [optionsAttempt, setOptionsAttempt] = useState(0);
  const [selectedKeys, setSelectedKeys] = useState<string[]>([]);
  const [generateStatus, setGenerateStatus] = useState<"idle" | "processing" | "success" | "failed">("idle");
  const [generateMessage, setGenerateMessage] = useState<string | null>(null);
  const [isGenerating, startGenerate] = useTransition();

  // Elapsed-time tickers drive stage progress + slow-loading notices.
  const optionsElapsed = useElapsedSeconds(optionsStatus === "loading", optionsAttempt);
  const generateElapsed = useElapsedSeconds(generateStatus === "processing");

  const groupNameRef = useRef<HTMLInputElement>(null);

  const summary = preview?.import_summary ?? EMPTY_IMPORT_SUMMARY;

  const selectedFileSummary = useMemo(
    () => selectedFiles.map((f) => `${f.name} (${Math.round(f.size / 1024)} KB)`),
    [selectedFiles],
  );

  // Highest step the user can reach
  const maxReached = useMemo(() => {
    let m = 0;
    if (groupName.trim()) m = 1;
    if (uploadStatus === "success" && preview) m = Math.max(m, 2);
    if (preview) m = Math.max(m, 2);
    if (generateStatus === "success") m = 4;
    return m;
  }, [groupName, uploadStatus, preview, generateStatus]);

  // Load disease options with explicit status. A previous version swallowed the
  // error in .catch(), so a failed/slow/empty response left the UI stuck on
  // "กำลังโหลดรายการบริการ..." forever. Now every outcome is terminal:
  // loading → success(with data) / success(empty) / error(retryable).
  const loadOptions = useCallback(async () => {
    setOptionsStatus("loading");
    setOptionsError(null);
    setOptionsAttempt((n) => n + 1);
    debugLog("options.fetch.start", { endpoint: "/api/target-groups/disease-options" });
    try {
      const opts = await getDiseaseOptions();
      setDiseaseOptions(opts);
      setOptionsStatus("success");
      debugLog("options.fetch.success", { optionCount: opts.length });
    } catch (err) {
      const message = getApiErrorMessage(err, "โหลดรายการโรค/บริการไม่สำเร็จ");
      setDiseaseOptions([]);
      setOptionsStatus("error");
      setOptionsError(message);
      debugLog("options.fetch.error", { message });
    }
  }, []);

  // Load disease options lazily on first reach of step 4 (idle → loading).
  useEffect(() => {
    if (pageIdx === 3 && optionsStatus === "idle") {
      void loadOptions();
    }
  }, [pageIdx, optionsStatus, loadOptions]);

  // Focus group name input on step 1
  useEffect(() => {
    if (pageIdx === 0) groupNameRef.current?.focus();
  }, [pageIdx]);

  function canAdvance() {
    if (pageIdx === 0) return groupName.trim().length > 0;
    if (pageIdx === 1) return uploadStatus === "success" && !!preview;
    if (pageIdx === 2) return !!preview;
    if (pageIdx === 3) return generateStatus === "success";
    return false;
  }

  function next() {
    if (canAdvance()) setPageIdx((i) => Math.min(i + 1, STEPS.length - 1));
  }

  function back() {
    setPageIdx((i) => Math.max(i - 1, 0));
  }

  function jump(idx: number) {
    if (idx <= maxReached || idx <= pageIdx + 1) setPageIdx(idx);
  }

  function handleUpload(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!groupName.trim()) return;
    // Guard double-submit: one in-flight upload at a time. Prevents a rapid
    // second click from creating a duplicate target_group_jobs row / hitting
    // SQLite "database is locked".
    if (isUploading || uploadStatus === "processing") return;
    if (selectedFiles.length === 0) return;
    const formData = new FormData();
    formData.append("group_name", groupName.trim());
    for (const file of selectedFiles) {
      formData.append("files", file);
    }
    const requestedGroupName = groupName.trim();
    setRecoveredGroupId(null);
    startUpload(async () => {
      const startedAt = Date.now();
      setUploadStatus("processing");
      setUploadMessage("กำลังอัปโหลดไฟล์ ตรวจสอบ CID และสร้างตัวอย่างข้อมูล");
      debugLog("upload.started", { fileCount: selectedFiles.length });
      try {
        const response = await uploadTargetGroupFiles(formData);
        setPreview(response);
        setUploadStatus("success");
        setUploadMessage(
          "อัปโหลดสำเร็จ "
          + response.source_file_count
          + " ไฟล์ รวม "
          + formatNumber(response.total_rows)
          + " แถว",
        );
        console.info("[upload] completed", { durationMs: Date.now() - startedAt, fileCount: selectedFiles.length });
      } catch (err) {
        const apiErr = err instanceof ApiError ? err : null;
        console.warn("[upload] failed", {
          durationMs: Date.now() - startedAt,
          status: apiErr?.status ?? 0,
          kind: apiErr?.kind,
        });

        // 409 — backend rejected a duplicate (same files + group name already
        // imported). Not a real failure: guide the user to the existing group.
        if (apiErr?.status === 409) {
          const detail = (apiErr.payload as { detail?: { group_id?: string } } | undefined)?.detail;
          if (detail?.group_id) setRecoveredGroupId(detail.group_id);
          setUploadStatus("failed");
          setUploadMessage("กลุ่มเป้าหมายนี้ถูกนำเข้าไปแล้ว — เปิดดูจากปุ่มด้านล่างหรือรายการกลุ่มเป้าหมายล่าสุด");
          return;
        }

        // Timeout — the backend may still be importing a large file. Reconcile
        // against recent groups before telling the user it failed; never auto-retry.
        if (apiErr?.kind === "timeout") {
          setUploadMessage("ไฟล์นี้ใช้เวลานำเข้านานกว่าปกติ ระบบกำลังตรวจสอบว่างานนำเข้าสำเร็จหรือยัง กรุณารอสักครู่");
          try {
            const groups = await listTargetGroups();
            const match = [...groups]
              .filter((g) => g.group_name === requestedGroupName)
              .sort((a, b) => (a.uploaded_at < b.uploaded_at ? 1 : -1))[0];
            setUploadStatus("failed");
            if (match) {
              setRecoveredGroupId(match.group_id);
              setUploadMessage("พบงานนำเข้าล่าสุดแล้ว — เปิดดูกลุ่มเป้าหมายเพื่อตรวจสอบและทำขั้นต่อไป (ไม่ต้องอัปโหลดซ้ำ)");
            } else {
              setUploadMessage("ไม่พบงานนำเข้าที่เสร็จสมบูรณ์ สามารถลองใหม่ได้ แต่โปรดตรวจสอบว่าไม่มีงานเดิมกำลังทำงานอยู่ก่อนกดซ้ำ");
            }
          } catch {
            setUploadStatus("failed");
            setUploadMessage("ไฟล์นี้ใช้เวลานานเกินกำหนด และตรวจสอบสถานะล่าสุดไม่สำเร็จ กรุณาเปิดรายการกลุ่มเป้าหมายเพื่อตรวจสอบก่อนลองใหม่");
          }
          return;
        }

        setUploadStatus("failed");
        setUploadMessage(apiErr ? apiErr.detail : "อัปโหลดไม่สำเร็จ");
      }
    });
  }

  function handleGenerate() {
    if (!preview || selectedKeys.length === 0) return;
    if (isGenerating || generateStatus === "processing") return; // guard double-fire
    debugLog("generate.start", { serviceCount: selectedKeys.length });
    startGenerate(async () => {
      setGenerateStatus("processing");
      setGenerateMessage("กำลัง normalize ตัวระบุและจับคู่กับฐานข้อมูลการตรวจโรค...");
      try {
        await generateResults(preview.group_id, selectedKeys);
        debugLog("generate.success", { serviceCount: selectedKeys.length });
        setGenerateStatus("success");
        setGenerateMessage(
          "สร้างผลลัพธ์สำเร็จ • "
          + formatNumber(summary.valid_cid_rows)
          + " รายการ • "
          + selectedKeys.length
          + " บริการ",
        );
      } catch (err) {
        const message = err instanceof ApiError ? err.detail : "สร้างผลลัพธ์ไม่สำเร็จ";
        debugLog("generate.error", { message });
        setGenerateStatus("failed");
        setGenerateMessage(message);
      }
    });
  }

  function toggleService(key: string) {
    setSelectedKeys((prev) => (prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]));
    if (generateStatus === "success") {
      setGenerateStatus("idle");
      setGenerateMessage(null);
    }
  }

  const step = STEPS[pageIdx];

  return (
    <div className="stack-layout">
      {/* Stepper header panel */}
      <section className="panel">
        <div className="panel-head">
          <div>
            <p className="eyebrow">{"Target group workflow"}</p>
            <h3>{"ขั้นตอนการสร้างกลุ่มเป้าหมาย"}</h3>
          </div>
          <span className="status-chip muted">{"ขั้นที่ "}{pageIdx + 1}{" / "}{STEPS.length}</span>
        </div>
        <p className="summary-copy">
          {"ทำตามลำดับด้านล่างเพื่อให้ระบบเก็บ provenance ครบทุกขั้น ระบบจะไม่ข้ามขั้นตอนหรือเดาข้อมูลแทนผู้ใช้"}
        </p>
        <HorizontalStepper currentIdx={pageIdx} maxReached={maxReached} onJump={jump} />
      </section>

      {/* Active step panel */}
      <section className="panel">
        <p className="eyebrow">{"ขั้นที่ "}{pageIdx + 1}</p>
        <h3>{step.label}</h3>
        <p className="summary-copy">{step.hint}</p>

        <div className="page-content">
          {/* Step 1 - Name */}
          {step.id === "name" && (
            <div className="stack-form">
              <label>
                <span>{"ชื่อกลุ่มเป้าหมาย"}</span>
                <input
                  ref={groupNameRef}
                  value={groupName}
                  onChange={(e) => setGroupName(e.target.value)}
                  placeholder={"เช่น คัดกรองมะเร็งปากมดลูก ไตรมาส 2/2569"}
                  onKeyDown={(e) => { if (e.key === "Enter" && groupName.trim()) next(); }}
                />
              </label>
            </div>
          )}

          {/* Step 2 - Upload */}
          {step.id === "upload" && (
            <form className="stack-form" onSubmit={handleUpload}>
              <label>
                <span>{"ไฟล์ต้นทาง (Excel / CSV / PDF)"}</span>
                <input
                  type="file"
                  name="files"
                  multiple
                  accept={ACCEPTED_TYPES}
                  onChange={(e) => setSelectedFiles(Array.from(e.currentTarget.files ?? []))}
                />
              </label>
              <p className="summary-copy">{"ชนิดไฟล์ที่รองรับ: Excel (.xlsx, .xls), CSV (.csv), PDF (.pdf)"}</p>
              <p className="upload-privacy-note">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" aria-hidden="true" style={{ flexShrink: 0, marginTop: 1 }}>
                  <rect x="3" y="11" width="18" height="11" rx="2" />
                  <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                </svg>
                {"ไฟล์ที่อัปโหลดจะถูกประมวลผลบนเซิร์ฟเวอร์ภายในหน่วยงานเท่านั้น ไม่มีการส่งข้อมูลผู้ป่วยออกสู่อินเทอร์เน็ต"}
              </p>
              {selectedFileSummary.length > 0 && (
                <div className="subtle-box">
                  <p className="summary-copy">{"รายการไฟล์ที่เลือก"}</p>
                  {selectedFiles.map((f, i) => (
                    <p key={getSelectedFileKey(f) || `${f.name}:${i}`}>{selectedFileSummary[i]}</p>
                  ))}
                </div>
              )}
              <div className="button-row">
                <button
                  className="primary-button"
                  type="submit"
                  disabled={isUploading || selectedFiles.length === 0}
                >
                  {isUploading
                    ? "กำลังอัปโหลด..."
                    : uploadStatus === "success"
                      ? "อัปโหลดใหม่"
                      : "อัปโหลดและตรวจตัวอย่าง"}
                </button>
              </div>
              {uploadStatus !== "idle" && uploadMessage && (
                <JobProgressCard
                  title={"สถานะการนำเข้ากลุ่มเป้าหมาย"}
                  status={
                    uploadStatus === "processing" ? "processing" :
                    uploadStatus === "success" ? "success" : "failed"
                  }
                  message={uploadMessage}
                  currentStage={
                    uploadStatus === "processing"
                      ? "กำลังอัปโหลดไฟล์ ตรวจสอบ CID และสร้างตัวอย่างข้อมูล"
                      : uploadStatus === "success"
                        ? "เสร็จสิ้น"
                        : "พบข้อผิดพลาด"
                  }
                  processedRows={uploadStatus === "success" ? summary.parsed_rows : null}
                  totalRows={uploadStatus === "success" ? (preview?.total_rows ?? null) : null}
                />
              )}
              {recoveredGroupId ? (
                <div className="button-row section-block">
                  <button
                    type="button"
                    className="primary-button"
                    onClick={() => router.push(`/target-groups/detail?id=${recoveredGroupId}`)}
                  >
                    {"เปิดกลุ่มเป้าหมายที่นำเข้าแล้ว"}
                  </button>
                </div>
              ) : null}
            </form>
          )}

          {/* Step 3 - Preview */}
          {step.id === "preview" && preview && (
            <div className="stack-layout">
              <div className="subtle-box">
                <p>
                  {"แถว parse สำเร็จ: "}{formatNumber(summary.parsed_rows)}{" / "}{formatNumber(preview.total_rows)}
                </p>
                <p>
                  {"CID ใช้งานได้: "}{formatNumber(summary.valid_cid_rows)}
                  {" • CID หาย: "}{formatNumber(summary.missing_cid_rows)}
                  {" • CID ไม่ผ่านเกณฑ์: "}{formatNumber(summary.invalid_cid_rows)}
                  {" • CID ซ้ำ: "}{formatNumber(summary.duplicate_cid_rows)}
                </p>
              </div>
              <div className="subtle-box">
                <p className="summary-copy">{"สถานะต่อไฟล์"}</p>
                {preview.uploaded_files.map((f) => (
                  <div key={getTargetGroupFileKey(f)}>
                    <p>
                      {f.file_name}{" • "}{f.file_type}{" • "}{f.parse_status ?? "-"}{" • "}{f.row_count ?? 0}{" แถว"}
                    </p>
                    {f.parse_error_summary ? (
                      <p className="summary-copy">{f.parse_error_summary}</p>
                    ) : null}
                  </div>
                ))}
              </div>
              <p className="summary-copy">
                {"ตัวอย่าง "}{preview.preview_rows.length}{" แถวแรกจากทั้งหมด "}{formatNumber(preview.total_rows)}{" แถว"}
              </p>
              <TargetGroupPreviewTable rows={preview.preview_rows} />
              {preview.validation_issues.length > 0 && (
                <div className="subtle-box">
                  <p className="summary-copy">
                    {"รายการที่ต้องตรวจสอบ ("}{preview.validation_issues.length}{")"}
                  </p>
                  {preview.validation_issues.map((issue) => (
                    <p key={getValidationIssueKey(issue)}>
                      {"แถว "}{issue.row_no}{": "}{issue.message}
                    </p>
                  ))}
                  <p className="summary-copy">
                    {"แถวที่มีปัญหาจะคงอยู่ใน staging และจะไม่ถูก merge เข้าฐานข้อมูลโดยอัตโนมัติ"}
                  </p>
                </div>
              )}
            </div>
          )}

          {/* Step 4 - Generate */}
          {step.id === "generate" && (
            <div className="stack-layout">
              <p className="summary-copy">
                {"เลือกรายการโรคหรือบริการที่ต้องการจับคู่กับฐานข้อมูลการตรวจโรค สามารถเลือกได้มากกว่าหนึ่งรายการ"}
              </p>
              {optionsStatus === "success" && diseaseOptions.length > 0 ? (
                <div className="service-selector-grid">
                  {diseaseOptions.map((opt) => (
                    <ServiceChip
                      key={opt.key}
                      option={opt}
                      checked={selectedKeys.includes(opt.key)}
                      onChange={() => toggleService(opt.key)}
                    />
                  ))}
                </div>
              ) : null}

              {optionsStatus === "loading" || optionsStatus === "idle" ? (
                <StageProgress
                  title="กำลังโหลดรายการโรค/บริการ"
                  stages={["โหลดรายการโรค/บริการจากฐานข้อมูลการตรวจโรค"]}
                  currentIndex={0}
                  status="loading"
                  elapsedSeconds={optionsElapsed}
                  onRetry={() => void loadOptions()}
                />
              ) : null}

              {optionsStatus === "error" ? (
                <StageProgress
                  title="ไม่สามารถโหลดรายการโรค/บริการได้"
                  stages={["โหลดรายการโรค/บริการจากฐานข้อมูลการตรวจโรค"]}
                  currentIndex={0}
                  status="error"
                  elapsedSeconds={optionsElapsed}
                  errorMessage={optionsError}
                  onRetry={() => void loadOptions()}
                />
              ) : null}

              {optionsStatus === "success" && diseaseOptions.length === 0 ? (
                <div className="subtle-box">
                  <p className="summary-copy">
                    {"ยังไม่พบรายการโรค/บริการในระบบ (แคตตาล็อกการคัดกรอง) — หากเพิ่งติดตั้งใหม่ ให้เปิดหน้า Dashboard เพื่อโหลด/ซิงก์ฐานข้อมูลการคัดกรอง แล้วกดโหลดรายการใหม่"}
                  </p>
                  <div className="button-row section-block">
                    <button className="secondary-button" type="button" onClick={() => void loadOptions()}>
                      {"โหลดรายการใหม่"}
                    </button>
                    <a className="secondary-button compact-button" href="/dashboard">
                      {"ไปหน้า Dashboard"}
                    </a>
                  </div>
                </div>
              ) : null}
              {selectedKeys.length === 0 && generateStatus !== "idle" && (
                <p className="feedback-line is-error">{"ต้องเลือกอย่างน้อย 1 รายการก่อนสร้างผลลัพธ์"}</p>
              )}
              <div className="button-row">
                <button
                  className="primary-button"
                  type="button"
                  disabled={isGenerating || generateStatus === "success" || selectedKeys.length === 0}
                  onClick={handleGenerate}
                >
                  {isGenerating
                    ? "กำลังสร้างผลลัพธ์..."
                    : generateStatus === "success"
                      ? "สร้างผลลัพธ์แล้ว"
                      : "สร้างผลลัพธ์"}
                </button>
              </div>
              {generateStatus === "processing" ? (
                <StageProgress
                  title="กำลังสร้างผลลัพธ์"
                  stages={GENERATE_STAGES}
                  currentIndex={Math.min(Math.floor(generateElapsed / 2), GENERATE_STAGES.length - 1)}
                  status="loading"
                  elapsedSeconds={generateElapsed}
                />
              ) : null}
              {(generateStatus === "success" || generateStatus === "failed") && generateMessage ? (
                <JobProgressCard
                  title={"สร้างผลลัพธ์"}
                  status={generateStatus === "success" ? "success" : "failed"}
                  message={generateMessage}
                  currentStage={generateStatus === "success" ? "เสร็จสิ้น" : "พบข้อผิดพลาด"}
                  processedRows={generateStatus === "success" ? summary.valid_cid_rows : null}
                  totalRows={generateStatus === "success" ? summary.valid_cid_rows : null}
                />
              ) : null}
              {generateStatus === "failed" ? (
                <div className="button-row section-block">
                  <button
                    className="secondary-button"
                    type="button"
                    disabled={isGenerating}
                    onClick={handleGenerate}
                  >
                    {"ลองสร้างผลลัพธ์ใหม่"}
                  </button>
                </div>
              ) : null}
            </div>
          )}

          {/* Step 5 - Review & export */}
          {step.id === "review" && preview && (
            <div className="stack-layout">
              <div className="subtle-box">
                <p>{"ผลลัพธ์พร้อมแล้ว สามารถเปิดหน้ารายการเพื่อ filter / ส่งออกได้"}</p>
              </div>
              <div className="button-row">
                <button
                  className="primary-button"
                  type="button"
                  onClick={() => router.push(`/target-groups/detail?id=${preview.group_id}`)}
                >
                  {"เปิดหน้าผลลัพธ์"}
                </button>
                <a
                  className="secondary-button compact-button"
                  href={`/api/target-groups/${preview.group_id}/export?format=xlsx`}
                  download
                >
                  {"ส่งออก Excel"}
                </a>
              </div>

              <div className="edit-back-card">
                <p className="eyebrow">{"ต้องการปรับข้อมูลย้อนหลัง?"}</p>
                <p className="summary-copy">
                  {"สามารถย้อนกลับไปแก้ไขขั้นใดก็ได้ ระบบจะเก็บการเปลี่ยนแปลงไว้ใน staging และต้องสร้างผลลัพธ์ใหม่อีกครั้งก่อนส่งออก"}
                </p>
                <div className="edit-back-grid">
                  <button type="button" className="edit-back-item" onClick={() => jump(0)}>
                    <span className="edit-back-num">{"01"}</span>
                    <span>
                      <strong>{"แก้ไขชื่อกลุ่ม"}</strong>
                      <span className="table-secondary-text">{"เปลี่ยนชื่อกลุ่มเป้าหมายและ metadata"}</span>
                    </span>
                  </button>
                  <button type="button" className="edit-back-item" onClick={() => jump(1)}>
                    <span className="edit-back-num">{"02"}</span>
                    <span>
                      <strong>{"เพิ่ม / เปลี่ยนไฟล์ต้นทาง"}</strong>
                      <span className="table-secondary-text">{"อัปโหลดไฟล์เพิ่มเติมหรือแทนที่ไฟล์เดิม"}</span>
                    </span>
                  </button>
                  <button type="button" className="edit-back-item" onClick={() => jump(2)}>
                    <span className="edit-back-num">{"03"}</span>
                    <span>
                      <strong>{"ปรับข้อมูลกลุ่มเป้าหมาย"}</strong>
                      <span className="table-secondary-text">{"แก้ CID / ชื่อ ที่ติด validation ใน staging"}</span>
                    </span>
                  </button>
                  <button type="button" className="edit-back-item" onClick={() => jump(3)}>
                    <span className="edit-back-num">{"04"}</span>
                    <span>
                      <strong>{"เปลี่ยนรายการโรค / บริการ"}</strong>
                      <span className="table-secondary-text">{"เลือกโรคหรือบริการใหม่ แล้วสร้างผลลัพธ์อีกครั้ง"}</span>
                    </span>
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Back / Next navigation */}
        <div className="page-nav">
          <button
            type="button"
            className="secondary-button"
            onClick={back}
            disabled={pageIdx === 0}
          >
            {"← ย้อนกลับ"}
          </button>
          <button
            type="button"
            className="primary-button"
            onClick={next}
            disabled={!canAdvance() || pageIdx === STEPS.length - 1}
          >
            {"ถัดไป →"}
          </button>
        </div>
      </section>

      {/* Recent groups */}
      <section className="panel">
        <p className="eyebrow">{"Recent groups"}</p>
        <h3>{"กลุ่มเป้าหมายล่าสุด"}</h3>
        {!recentGroups.length ? (
          <p className="summary-copy">{"ยังไม่มีกลุ่มเป้าหมายที่อัปโหลดไว้"}</p>
        ) : (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>{"ชื่อกลุ่ม"}</th>
                  <th>{"ไฟล์ต้นทาง"}</th>
                  <th>{"จำนวนไฟล์"}</th>
                  <th>{"จำนวนแถว"}</th>
                  <th>{"จับคู่ได้"}</th>
                  <th>{"อัปโหลดเมื่อ"}</th>
                  <th>{"เปิดดู"}</th>
                </tr>
              </thead>
              <tbody>
                {recentGroups.map((group) => (
                  <tr key={group.group_id}>
                    <td>{group.group_name}</td>
                    <td>{group.source_file_name}</td>
                    <td>{group.source_file_count}</td>
                    <td>{formatNumber(group.total_rows)}</td>
                    <td>{formatNumber(group.match_summary.matched)}</td>
                    <td>{formatDate(group.uploaded_at)}</td>
                    <td>
                      <Link href={`/target-groups/detail?id=${group.group_id}`}>{"เปิดกลุ่ม"}</Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
