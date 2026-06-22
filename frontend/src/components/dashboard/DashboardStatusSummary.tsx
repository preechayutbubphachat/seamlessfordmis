import type React from "react";

import { formatDate, formatNumber } from "@/lib/format";
import type { SystemStatus } from "@/types/system";

const metricIconProps = {
  width: 22,
  height: 22,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.8,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
};

function MetricCard({
  icon,
  label,
  value,
  note,
}: {
  icon: React.ReactNode;
  label: string;
  value: string | number;
  note?: string;
}) {
  return (
    <div className="summary-card">
      <span className="summary-card-icon" aria-hidden="true">
        {icon}
      </span>
      <div>
        <p className="summary-card-label">{label}</p>
        <p className="summary-card-value">
          {typeof value === "number" ? formatNumber(value) : value}
        </p>
        {note && <p className="summary-card-note">{note}</p>}
      </div>
    </div>
  );
}

export function DashboardStatusSummary({ status }: { status: SystemStatus }) {
  const importIdShort = status.latest_import_job_id
    ? status.latest_import_job_id.slice(0, 4) + "..." + status.latest_import_job_id.slice(9, 13) + "..."
    : "-";

  return (
    <section className="panel db-status-panel">
      <div className="panel-head">
        <div>
          <p className="eyebrow">สถานะระบบ</p>
          <h3>สถานะฐานข้อมูลการคัดกรอง</h3>
        </div>
        <span className={`status-chip ${status.dataset_ready ? "ready" : "warning"}`}>
          {status.dataset_ready ? "พร้อมใช้งาน" : "ยังไม่พร้อม"}
        </span>
      </div>
      <div className="summary-grid">
        <MetricCard
          icon={<svg {...metricIconProps}><path d="M4 7.5C4 5.57 7.58 4 12 4s8 1.57 8 3.5S16.42 11 12 11 4 9.43 4 7.5Z" /><path d="M4 7.5v4c0 1.93 3.58 3.5 8 3.5s8-1.57 8-3.5v-4" /><path d="M4 11.5v4c0 1.93 3.58 3.5 8 3.5s8-1.57 8-3.5v-4" /></svg>}
          label="ไฟล์ต้นทางทั้งหมด"
          value={status.source_file_count ?? "-"}
          note="ไฟล์"
        />
        <MetricCard
          icon={<svg {...metricIconProps}><path d="M16 21v-2a4 4 0 0 0-8 0v2" /><circle cx="12" cy="7" r="4" /><path d="M22 21v-2a4 4 0 0 0-3-3.87" /><path d="M16 3.13a4 4 0 0 1 0 7.75" /></svg>}
          label="จำนวนผู้ป่วย"
          value={status.row_counts.patients ?? "-"}
          note="ราย"
        />
        <MetricCard
          icon={<svg {...metricIconProps}><path d="M9 12h6" /><path d="M12 9v6" /><path d="M7 3h10v4H7z" /><path d="M5 7h14v14H5z" /></svg>}
          label="รายการบริการ"
          value={status.row_counts.disease_screening_records ?? "-"}
          note="รายการ"
        />
        <MetricCard
          icon={<svg {...metricIconProps}><path d="M21 12a9 9 0 1 1-2.64-6.36" /><path d="M21 3v6h-6" /></svg>}
          label="Import ล่าสุด (ID)"
          value={importIdShort}
          note={status.import_status ?? "-"}
        />
        <MetricCard
          icon={<svg {...metricIconProps}><path d="M8 2v4" /><path d="M16 2v4" /><path d="M3 10h18" /><rect x="3" y="4" width="18" height="18" rx="2" /></svg>}
          label="อัปเดตล่าสุด"
          value={formatDate(status.fingerprint?.modified_at ?? null)}
          note={status.source_file_changed ? "มีการเปลี่ยนแปลง" : "ตรงกับฐานข้อมูล"}
        />
      </div>
    </section>
  );
}
