"use client";

import { Fragment, useState, useTransition } from "react";

import { downloadScreeningImportReport, getApiErrorMessage, getScreeningImportDetail } from "@/lib/api";
import { formatDate, formatNumber } from "@/lib/format";
import type { ImportJobDetail, ImportJobSummary } from "@/types/screening-database";

function ImportStatusBadge({ status }: { status: string }) {
  const map: Record<string, { label: string; cls: string }> = {
    success: { label: "สำเร็จ", cls: "ready" },
    completed: { label: "สำเร็จ", cls: "ready" },
    processing: { label: "กำลังนำเข้า", cls: "accent" },
    running: { label: "กำลังนำเข้า", cls: "accent" },
    pending: { label: "รอตรวจสอบ", cls: "muted" },
    staged: { label: "รอตรวจสอบ", cls: "muted" },
    warning: { label: "เตือน", cls: "warning" },
    partial: { label: "เตือน", cls: "warning" },
    failed: { label: "ล้มเหลว", cls: "danger" },
    error: { label: "ล้มเหลว", cls: "danger" },
  };
  const cfg = map[status.toLowerCase()] ?? { label: status || "-", cls: "muted" };
  return <span className={`status-chip ${cfg.cls}`}>{cfg.label}</span>;
}

function FileTypeTag({ fileType }: { fileType: string }) {
  const normalized = fileType.toLowerCase();
  const label =
    normalized === "excel"
      ? "Excel"
      : normalized === "csv"
        ? "CSV"
        : normalized === "pdf"
          ? "PDF"
          : fileType || "-";
  return <span className={`db-filetype-tag ${normalized}`}>{label}</span>;
}

function EmptyState() {
  return (
    <div className="empty-state-box db-import-empty">
      <p>ยังไม่มีประวัติการนำเข้าข้อมูล</p>
      <p>กด "เพิ่มข้อมูลการคัดกรอง" หรือ "ซิงก์ฐานข้อมูล" เพื่อเริ่มต้น</p>
    </div>
  );
}

function ActionIcon({ type }: { type: "view" | "download" | "more" }) {
  if (type === "view") {
    return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z" /><circle cx="12" cy="12" r="3" /></svg>;
  }
  if (type === "download") {
    return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M12 3v12" /><path d="m7 10 5 5 5-5" /><path d="M5 21h14" /></svg>;
  }
  return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><circle cx="12" cy="12" r="1" /><circle cx="19" cy="12" r="1" /><circle cx="5" cy="12" r="1" /></svg>;
}

function DetailPanel({ detail }: { detail: ImportJobDetail }) {
  return (
    <div className="db-import-detail">
      <dl className="db-import-detail-grid">
        <div><dt>Import ID</dt><dd>{detail.import_id}</dd></div>
        <div><dt>ไฟล์ต้นทาง</dt><dd>{detail.source_files.length || detail.file_name}</dd></div>
        <div><dt>แถวที่ parse ได้</dt><dd>{formatNumber(detail.parsed_rows)}</dd></div>
        <div><dt>แถวถูกต้อง</dt><dd>{formatNumber(detail.valid_rows)}</dd></div>
        <div><dt>คำเตือน</dt><dd>{formatNumber(detail.warning_rows)}</dd></div>
        <div><dt>ผิดพลาด</dt><dd>{formatNumber(detail.invalid_rows)}</dd></div>
      </dl>
      {detail.source_files.length > 0 && (
        <ul className="db-import-file-list">
          {detail.source_files.slice(0, 6).map((file) => (
            <li key={file.file_id ?? file.file_name}>
              <span>{file.file_name}</span>
              <span>{file.parse_status ?? "-"} · {formatNumber(file.row_count)} แถว</span>
            </li>
          ))}
        </ul>
      )}
      {detail.error_summary && <p className="db-import-error">{detail.error_summary}</p>}
    </div>
  );
}

export function RecentImportsTable({
  imports,
  total,
}: {
  imports: ImportJobSummary[];
  total: number;
}) {
  const [activeDetail, setActiveDetail] = useState<ImportJobDetail | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busyImportId, setBusyImportId] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  function handleView(importId: string) {
    startTransition(async () => {
      setBusyImportId(importId);
      setMessage(null);
      try {
        const detail = await getScreeningImportDetail(importId);
        setActiveDetail((prev) => (prev?.import_id === detail.import_id ? null : detail));
      } catch (error) {
        setMessage(getApiErrorMessage(error, "โหลดรายละเอียด import ไม่สำเร็จ"));
      } finally {
        setBusyImportId(null);
      }
    });
  }

  function handleDownloadReport(importId: string) {
    startTransition(async () => {
      setBusyImportId(importId);
      setMessage(null);
      try {
        const result = await downloadScreeningImportReport(importId);
        setMessage(`ดาวน์โหลดรายงานแล้ว: ${result.filename}`);
      } catch (error) {
        setMessage(getApiErrorMessage(error, "ดาวน์โหลดรายงานไม่สำเร็จ"));
      } finally {
        setBusyImportId(null);
      }
    });
  }

  return (
    <section className="panel db-imports-panel">
      <div className="panel-head">
        <div>
          <p className="eyebrow">ประวัติการนำเข้า</p>
          <h3>ประวัติการนำเข้าล่าสุด</h3>
        </div>
        {total > 0 && <span className="status-chip muted">{formatNumber(total)} รายการ</span>}
      </div>

      {message && <p className="db-card-feedback">{message}</p>}

      {imports.length === 0 ? (
        <EmptyState />
      ) : (
        <div className="db-table-wrapper">
          <table className="db-imports-table">
            <thead>
              <tr>
                <th>วันที่และเวลา</th>
                <th>ไฟล์ที่นำเข้า</th>
                <th>ประเภทไฟล์</th>
                <th>สถานะ</th>
                <th style={{ textAlign: "right" }}>แถวข้อมูลที่ตรวจพบ</th>
                <th>นำเข้าโดย</th>
                <th>การดำเนินการ</th>
              </tr>
            </thead>
            <tbody>
              {imports.map((job) => (
                <Fragment key={job.import_id}>
                  <tr key={job.import_id}>
                    <td className="db-cell-date">
                      <span>{formatDate(job.created_at)}</span>
                      {job.created_at && (
                        <span className="db-cell-time">
                          {new Date(job.created_at).toLocaleTimeString("th-TH", {
                            hour: "2-digit",
                            minute: "2-digit",
                          })} น.
                        </span>
                      )}
                    </td>
                    <td className="db-cell-filename" title={job.file_name}>
                      {job.file_name.length > 34 ? job.file_name.slice(0, 30) + "..." : job.file_name}
                    </td>
                    <td><FileTypeTag fileType={job.file_type} /></td>
                    <td><ImportStatusBadge status={job.status} /></td>
                    <td style={{ textAlign: "right" }}>
                      <span className="db-cell-rows">{formatNumber(job.detected_rows)}</span>
                      {job.failed_rows > 0 && <span className="db-cell-failed"> ({job.failed_rows} ผิดพลาด)</span>}
                    </td>
                    <td style={{ color: "var(--muted)", fontSize: "0.84rem" }}>
                      {job.created_by ?? "ระบบอัตโนมัติ"}
                    </td>
                    <td>
                      <div className="db-actions-row">
                        <button
                          type="button"
                          className="db-action-btn"
                          title="ดูรายละเอียด import"
                          aria-label={`ดูรายละเอียด import ${job.import_id.slice(0, 8)}`}
                          disabled={isPending && busyImportId === job.import_id}
                          onClick={() => handleView(job.import_id)}
                        >
                          <ActionIcon type="view" />
                        </button>
                        <button
                          type="button"
                          className="db-action-btn"
                          title="ดาวน์โหลดรายงานสรุป import"
                          aria-label={`ดาวน์โหลดรายงานสรุป import ${job.import_id.slice(0, 8)}`}
                          disabled={isPending && busyImportId === job.import_id}
                          onClick={() => handleDownloadReport(job.import_id)}
                        >
                          <ActionIcon type="download" />
                        </button>
                        <button type="button" className="db-action-btn" title="ยังไม่มีเมนูเพิ่มเติม" aria-label="เมนูเพิ่มเติมยังไม่พร้อม" disabled><ActionIcon type="more" /></button>
                      </div>
                    </td>
                  </tr>
                  {activeDetail?.import_id === job.import_id && (
                    <tr key={`${job.import_id}-detail`} className="db-detail-row">
                      <td colSpan={7}><DetailPanel detail={activeDetail} /></td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {total > imports.length && (
        <p className="db-table-footnote">
          แสดง {imports.length} จาก {formatNumber(total)} รายการ
        </p>
      )}
    </section>
  );
}
