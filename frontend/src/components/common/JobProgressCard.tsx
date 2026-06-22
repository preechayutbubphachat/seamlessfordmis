type JobProgressCardProps = {
  title: string;
  status: "pending" | "processing" | "success" | "failed" | "warning";
  message: string;
  currentStage?: string | null;
  progressPercent?: number | null;
  processedRows?: number | null;
  totalRows?: number | null;
};

function getTone(status: JobProgressCardProps["status"]) {
  switch (status) {
    case "success":  return "ready";
    case "failed":   return "danger";
    case "warning":  return "warning";
    default:         return "accent";
  }
}

function getStatusLabel(status: JobProgressCardProps["status"]) {
  switch (status) {
    case "success":    return "เสร็จสิ้น";
    case "failed":     return "ไม่สำเร็จ";
    case "warning":    return "ต้องตรวจสอบ";
    case "processing": return "กำลังประมวลผล";
    default:           return "กำลังเริ่มต้น";
  }
}

export function JobProgressCard({
  title,
  status,
  message,
  currentStage,
  progressPercent,
  processedRows,
  totalRows,
}: JobProgressCardProps) {
  const tone = getTone(status);
  const isProcessing = status === "processing" || status === "pending";
  const hasCounts = typeof processedRows === "number" && typeof totalRows === "number";
  const pct =
    typeof progressPercent === "number"
      ? Math.max(0, Math.min(100, progressPercent))
      : hasCounts && totalRows! > 0
        ? Math.round((processedRows! / totalRows!) * 100)
        : status === "success" ? 100 : isProcessing ? 40 : 0;

  return (
    <section
      className={`panel progress-panel ${tone}`}
      aria-live="polite"
      style={{ marginTop: "14px" }}
    >
      <div className="loading-state">
        {isProcessing ? (
          <span className="loading-spinner" aria-hidden="true" />
        ) : null}
        <p className="progress-stage" style={{ margin: 0 }}>
          {currentStage ?? title}
        </p>
        <span
          className={`status-chip ${tone}`}
          style={{ marginLeft: "auto", flexShrink: 0 }}
        >
          {getStatusLabel(status)}
        </span>
      </div>
      <p className="summary-copy" style={{ marginTop: "8px" }}>
        {message}
      </p>
      <div
        className="progress-bar-shell"
        aria-label={`${pct}%`}
        style={{ marginTop: "12px" }}
      >
        <div
          className="progress-bar-fill"
          style={{ width: `${pct}%`, transition: "width 0.4s ease" }}
        />
      </div>
      {hasCounts ? (
        <p className="progress-meta">
          {"ประมวลผลแล้ว"}{" "}
          {processedRows!.toLocaleString("th-TH")}{" "}
          {"จาก"}{" "}
          {totalRows!.toLocaleString("th-TH")}{" "}
          {"รายการ"}
        </p>
      ) : null}
    </section>
  );
}
