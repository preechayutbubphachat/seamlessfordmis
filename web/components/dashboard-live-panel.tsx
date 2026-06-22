"use client";

import { useState, useTransition } from "react";

import { getSystemStatus, syncMainDataset } from "@/lib/api";
import { DatasetStatus, SyncResponse } from "@/types";

type Props = {
  initialStatus: DatasetStatus;
};

export function DashboardLivePanel({ initialStatus }: Props) {
  const [status, setStatus] = useState(initialStatus);
  const [syncResult, setSyncResult] = useState<SyncResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  function handleSync() {
    setError(null);
    setSyncResult(null);
    startTransition(async () => {
      try {
        const response = await syncMainDataset();
        const refreshedStatus = await getSystemStatus();
        setSyncResult(response);
        setStatus(refreshedStatus);
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "Failed to sync source dataset.");
      }
    });
  }

  return (
    <section className="panel stack-md">
      <div className="action-header">
        <div>
          <p className="panel-label">ซิงก์ข้อมูลทันที</p>
          <h2>อัปเดตฐานข้อมูลจากชุดไฟล์ Excel ปัจจุบัน</h2>
        </div>
        <button className="button" type="button" disabled={isPending} onClick={handleSync}>
          {isPending ? "กำลังซิงก์..." : "ซิงก์ข้อมูลตอนนี้"}
        </button>
      </div>

      <div className="stats-grid">
        <div>
          <p className="panel-label">สถานะฐานข้อมูล</p>
          <strong>{status.dataset_ready ? "พร้อมใช้งาน" : "ยังไม่พร้อม"}</strong>
        </div>
        <div>
          <p className="panel-label">การเปลี่ยนแปลงไฟล์</p>
          <strong>{status.source_file_changed ? "มีการเปลี่ยนแปลง" : "ไม่เปลี่ยนแปลง"}</strong>
        </div>
        <div>
          <p className="panel-label">งานนำเข้าล่าสุด</p>
          <strong>{status.last_completed_import_job_id ? `#${status.last_completed_import_job_id}` : "-"}</strong>
        </div>
      </div>

      {syncResult ? (
        <div className="callout tone-success stack-md">
          <p className="panel-label">ผลการซิงก์ล่าสุด</p>
          <p>
            งาน #{syncResult.job_id} เสร็จสมบูรณ์ นำเข้า {syncResult.imported_rows} แถว จาก {syncResult.file_count} ไฟล์
          </p>
          <p className="muted">
            Manifest {syncResult.manifest_hash_sha256.slice(0, 24)}... และพบข้อผิดพลาดระดับแถว {syncResult.error_rows} รายการ
          </p>
        </div>
      ) : null}

      {error ? <p className="error-text">{error}</p> : null}
    </section>
  );
}
