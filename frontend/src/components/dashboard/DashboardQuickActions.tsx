"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

import { JobProgressCard } from "@/components/common/JobProgressCard";
import { ApiError, downloadScreeningImportReport, syncDiseaseScreeningDatabase } from "@/lib/api";

type SyncState = "idle" | "loading" | "success" | "network_error" | "backend_error";

export function DashboardQuickActions({
  latestImportId,
  onSyncSuccess,
}: {
  latestImportId?: string | null;
  onSyncSuccess?: () => void;
}) {
  const router = useRouter();
  const [syncState, setSyncState] = useState<SyncState>("idle");
  const [message, setMessage] = useState<string | null>(null);
  const [summary, setSummary] = useState<{ successRows: number; totalRows: number } | null>(null);
  const [isPending, startTransition] = useTransition();

  function resetSync() {
    setSyncState("idle");
    setMessage(null);
    setSummary(null);
  }

  function handleSync() {
    startTransition(async () => {
      setSyncState("loading");
      setSummary(null);
      setMessage("กำลังตรวจไฟล์ต้นทางและซิงก์ฐานข้อมูลการตรวจโรค...");
      try {
        const response = await syncDiseaseScreeningDatabase();
        setSyncState("success");
        setSummary({ successRows: response.success_rows, totalRows: response.total_rows });
        setMessage(`ซิงก์สำเร็จ: ${response.success_rows} รายการ จากไฟล์ต้นทาง ${response.source_file_count} ไฟล์`);
        onSyncSuccess?.();
        router.refresh();
      } catch (error) {
        if (error instanceof ApiError) {
          setSyncState(error.kind === "network" ? "network_error" : "backend_error");
          setMessage(error.detail);
          return;
        }
        setSyncState("backend_error");
        setMessage("ซิงก์ไม่สำเร็จ กรุณาตรวจสอบ log และข้อความจาก backend");
      }
    });
  }

  function handleDownloadLatestReport() {
    if (!latestImportId) return;
    startTransition(async () => {
      setSyncState("loading");
      setSummary(null);
      setMessage("กำลังเตรียมรายงานสรุป import ล่าสุด...");
      try {
        const result = await downloadScreeningImportReport(latestImportId);
        setSyncState("success");
        setMessage(`ดาวน์โหลดรายงานแล้ว: ${result.filename}`);
      } catch (error) {
        setSyncState(error instanceof ApiError && error.kind === "network" ? "network_error" : "backend_error");
        setMessage(error instanceof ApiError ? error.detail : "ดาวน์โหลดรายงานไม่สำเร็จ");
      }
    });
  }

  return (
    <div className="db-actions-panel">
      <div className="db-quick-actions">
        <button
          type="button"
          className="secondary-button db-quick-btn primary-action"
          disabled={isPending}
          onClick={handleSync}
          title="ซิงก์ฐานข้อมูลการตรวจโรค"
        >
          <span className="db-btn-icon">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182m0-4.991v4.99" />
            </svg>
          </span>
          {isPending ? "กำลังซิงก์..." : "ซิงก์ฐานข้อมูลการตรวจโรค"}
        </button>

        <button
          type="button"
          className="secondary-button db-quick-btn"
          onClick={() => {
            document
              .querySelector(".db-integrity-list")
              ?.scrollIntoView({ behavior: "smooth", block: "center" });
          }}
          title="ใช้ปุ่มตรวจสอบไฟล์ล่าสุดใน Source Integrity card เพื่อเรียก API ตรวจชุดไฟล์ใหม่"
        >
          <span className="db-btn-icon">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607Z" />
            </svg>
          </span>
          ตรวจสอบไฟล์ล่าสุด
        </button>

        <button
          type="button"
          className="secondary-button db-quick-btn"
          onClick={() => {
            document
              .querySelector(".db-imports-table")
              ?.scrollIntoView({ behavior: "smooth", block: "start" });
          }}
          title="ดูประวัติการนำเข้าทั้งหมด"
        >
          <span className="db-btn-icon">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 12h16.5m-16.5 3.75h16.5M3.75 19.5h16.5M5.625 4.5h12.75a1.875 1.875 0 0 1 0 3.75H5.625a1.875 1.875 0 0 1 0-3.75Z" />
            </svg>
          </span>
          ดูประวัติการนำเข้า
        </button>

        <button
          type="button"
          className="secondary-button db-quick-btn"
          disabled={!latestImportId || isPending}
          onClick={handleDownloadLatestReport}
          title={latestImportId ? "ดาวน์โหลดรายงานสรุป import ล่าสุด" : "ยังไม่มี import ล่าสุดให้ดาวน์โหลดรายงาน"}
        >
          <span className="db-btn-icon">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 12 12 16.5m0 0L7.5 12m4.5 4.5V3" />
            </svg>
          </span>
          ดาวน์โหลดรายงานสรุป
        </button>
      </div>

      {syncState !== "idle" && (
        <div style={{ marginTop: "14px" }}>
          <JobProgressCard
            title="สถานะการทำงาน"
            status={syncState === "loading" ? "processing" : syncState === "success" ? "success" : "failed"}
            message={message ?? ""}
            currentStage={syncState === "loading" ? "กำลังดำเนินการ" : syncState === "success" ? "เสร็จสิ้น" : "พบข้อผิดพลาด"}
            processedRows={summary?.successRows ?? null}
            totalRows={summary?.totalRows ?? null}
          />
          <button
            type="button"
            className="secondary-button compact-button"
            onClick={resetSync}
            style={{ marginTop: "10px" }}
          >
            รีเซ็ตสถานะ
          </button>
        </div>
      )}
    </div>
  );
}
