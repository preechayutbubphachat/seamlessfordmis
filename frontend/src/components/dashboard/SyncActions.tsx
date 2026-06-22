"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

import { JobProgressCard } from "@/components/common/JobProgressCard";
import { ApiError, syncDiseaseScreeningDatabase } from "@/lib/api";

type SyncState = "idle" | "loading" | "success" | "network_error" | "backend_error";

export function SyncActions() {
  const router = useRouter();
  const [syncState, setSyncState] = useState<SyncState>("idle");
  const [message, setMessage] = useState<string | null>(null);
  const [summary, setSummary] = useState<{ successRows: number; totalRows: number } | null>(null);
  const [isPending, startTransition] = useTransition();

  function reset() {
    setSyncState("idle");
    setMessage(null);
    setSummary(null);
  }

  return (
    <section className="panel action-panel">
      <p className="eyebrow">Sync action</p>
      <h3>{"ซิงก์ฐานข้อมูลการตรวจโรค"}</h3>
      <p className="summary-copy">
        {"ระบบจะโหลดไฟล์ต้นทางทั้งชุดใหม่และรีเฟรชสถานะบนแดชบอร์ดทันที หากนำเข้าไม่ผ่าน ระบบจะเก็บรายละเอียดไว้ให้ตรวจสอบต่อได้"}
      </p>
      <div className="button-row" style={{ marginTop: "14px" }}>
        <button
          className="primary-button"
          disabled={isPending}
          onClick={() =>
            startTransition(async () => {
              setSyncState("loading");
              setSummary(null);
              setMessage("กำลังตรวจไฟล์ต้นทางและซิงก์ฐานข้อมูลการตรวจโรค...");
              try {
                const response = await syncDiseaseScreeningDatabase();
                setSyncState("success");
                setSummary({ successRows: response.success_rows, totalRows: response.total_rows });
                setMessage(
                  `ซิงก์สำเร็จ: ${response.success_rows} รายการ จากไฟล์ต้นทาง ${response.source_file_count} ไฟล์`,
                );
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
            })
          }
        >
          {isPending ? "กำลังซิงก์..." : "ซิงก์ฐานข้อมูลการตรวจโรค"}
        </button>
        {syncState !== "idle" && (
          <button
            className="secondary-button"
            type="button"
            onClick={reset}
            disabled={isPending}
          >
            {"รีเซ็ตสถานะ"}
          </button>
        )}
      </div>
      {syncState !== "idle" && message ? (
        <JobProgressCard
          title="สถานะการซิงก์ข้อมูล"
          status={
            syncState === "loading" ? "processing" :
            syncState === "success" ? "success" : "failed"
          }
          message={message}
          currentStage={
            syncState === "loading"
              ? "กำลังตรวจสอบไฟล์ต้นทางและอัปเดตข้อมูลในระบบ"
              : syncState === "success"
                ? "เสร็จสิ้น"
                : "พบข้อผิดพลาด"
          }
          processedRows={summary?.successRows ?? null}
          totalRows={summary?.totalRows ?? null}
        />
      ) : null}
    </section>
  );
}
