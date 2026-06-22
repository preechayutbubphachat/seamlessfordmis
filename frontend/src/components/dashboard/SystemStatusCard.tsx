import { formatDate, formatNumber } from "@/lib/format";
import type { SystemStatus } from "@/types/system";

export function SystemStatusCard({ status }: { status: SystemStatus }) {
  return (
    <section className="panel">
      <div className="panel-head">
        <div>
          <p className="eyebrow">System status</p>
          <h3>สถานะฐานข้อมูลการตรวจโรค</h3>
        </div>
        <span className={`status-chip ${status.dataset_ready ? "ready" : "warning"}`}>
          {status.dataset_ready ? "พร้อมใช้งาน" : "ยังไม่พร้อม"}
        </span>
      </div>
      <dl className="key-grid">
        <div>
          <dt>สถานะซิงก์ล่าสุด</dt>
          <dd>{status.import_status ?? "-"}</dd>
        </div>
        <div>
          <dt>ไฟล์ต้นทางเปลี่ยนหรือไม่</dt>
          <dd>{status.source_file_changed ? "มีการเปลี่ยนแปลง" : "ยังไม่เปลี่ยน"}</dd>
        </div>
        <div>
          <dt>จำนวนไฟล์ต้นทาง</dt>
          <dd>{formatNumber(status.source_file_count)}</dd>
        </div>
        <div>
          <dt>ผู้ป่วย</dt>
          <dd>{formatNumber(status.row_counts.patients)}</dd>
        </div>
        <div>
          <dt>ประวัติการตรวจ/บริการ</dt>
          <dd>{formatNumber(status.row_counts.diagnosis_history)}</dd>
        </div>
        <div>
          <dt>Import job ล่าสุด</dt>
          <dd>{status.latest_import_job_id ?? "-"}</dd>
        </div>
        <div className="full-span">
          <dt>source-set hash</dt>
          <dd><code>{status.source_set_hash ?? "-"}</code></dd>
        </div>
        <div className="full-span">
          <dt>ไฟล์อ้างอิงแรก</dt>
          <dd>{status.fingerprint?.filename ?? "-"}</dd>
        </div>
        <div className="full-span">
          <dt>แก้ไขล่าสุด</dt>
          <dd>{formatDate(status.fingerprint?.modified_at ?? null)}</dd>
        </div>
      </dl>
    </section>
  );
}
