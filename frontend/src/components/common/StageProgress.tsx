"use client";

// Stage-based progress for loads/operations that do NOT expose real server-side
// progress. The percentage is derived purely from "which stage are we on",
// labelled clearly as ความคืบหน้าตามขั้นตอน so it is never mistaken for a real
// record count. Shows elapsed time, a slow-loading warning + retry after a
// threshold, and a terminal error state with retry. No CID / patient data here.

export type StageStatus = "loading" | "success" | "error";

type StageProgressProps = {
  title: string;
  stages: string[];
  /** 0-based index of the active (or last-completed on success) stage */
  currentIndex: number;
  status: StageStatus;
  elapsedSeconds: number;
  errorMessage?: string | null;
  onRetry?: () => void;
  /** seconds before the "taking longer than usual" notice appears */
  slowThresholdSec?: number;
  retryLabel?: string;
};

function clampPercent(value: number) {
  return Math.max(0, Math.min(100, Math.round(value)));
}

export function StageProgress({
  title,
  stages,
  currentIndex,
  status,
  elapsedSeconds,
  errorMessage,
  onRetry,
  slowThresholdSec = 15,
  retryLabel = "ลองโหลดใหม่",
}: StageProgressProps) {
  const total = Math.max(stages.length, 1);
  const safeIndex = Math.max(0, Math.min(currentIndex, total - 1));
  const stageNumber = safeIndex + 1;

  // Stage-based percent only. On success show 100%; while loading show progress
  // up to the current stage's midpoint so it never claims a stage is finished
  // before it is.
  const pct =
    status === "success"
      ? 100
      : status === "error"
        ? clampPercent((safeIndex / total) * 100)
        : clampPercent(((safeIndex + 0.5) / total) * 100);

  const tone = status === "success" ? "ready" : status === "error" ? "danger" : "accent";
  const isSlow = status === "loading" && elapsedSeconds >= slowThresholdSec;

  return (
    <section className={`panel progress-panel ${tone}`} aria-live="polite">
      <div className="loading-state">
        {status === "loading" ? <span className="loading-spinner" aria-hidden="true" /> : null}
        <p className="progress-stage" style={{ margin: 0 }}>
          {status === "error" ? title : `${title} • ขั้นตอน ${stageNumber}/${total}`}
        </p>
        <span className={`status-chip ${tone}`} style={{ marginLeft: "auto", flexShrink: 0 }}>
          {status === "success" ? "เสร็จสิ้น" : status === "error" ? "ไม่สำเร็จ" : "กำลังประมวลผล"}
        </span>
      </div>

      {status !== "error" ? (
        <p className="summary-copy" style={{ marginTop: "8px" }}>
          {stages[safeIndex] ?? title}
        </p>
      ) : null}

      <div className="progress-bar-shell" aria-label={`${pct}%`} style={{ marginTop: "12px" }}>
        <div className="progress-bar-fill" style={{ width: `${pct}%`, transition: "width 0.4s ease" }} />
      </div>

      <p className="progress-meta" style={{ marginTop: "8px" }}>
        {status === "error"
          ? "หยุดที่ขั้นตอน " + stageNumber + "/" + total
          : "ความคืบหน้าตามขั้นตอน (ไม่ใช่จำนวนรายการจริง) • ใช้เวลา " + elapsedSeconds + " วินาที"}
      </p>

      {status === "error" && errorMessage ? (
        <p className="feedback-line is-error" style={{ marginTop: "6px" }}>
          {errorMessage}
        </p>
      ) : null}

      {isSlow ? (
        <p className="summary-copy" style={{ marginTop: "6px" }}>
          {"โหลดนานกว่าปกติ กดลองใหม่หรือตรวจสอบฐานข้อมูลการคัดกรอง"}
        </p>
      ) : null}

      {onRetry && (status === "error" || isSlow) ? (
        <div className="button-row section-block">
          <button className="secondary-button" type="button" onClick={onRetry}>
            {retryLabel}
          </button>
        </div>
      ) : null}
    </section>
  );
}
