type LoadingStateProps = {
  title?: string;
  message?: string;
  compact?: boolean;
};

export function LoadingState({
  title = "โปรดรอสักครู่...",
  message = "กำลังโหลดข้อมูล...",
  compact = false,
}: LoadingStateProps) {
  return (
    <section className={`panel loading-panel ${compact ? "compact" : ""}`} aria-live="polite">
      <div className="loading-state">
        <span className="loading-spinner" aria-hidden="true" />
        <div>
          <p className="eyebrow">Loading</p>
          <h3>{title}</h3>
          <p className="summary-copy">{message}</p>
        </div>
      </div>
    </section>
  );
}
