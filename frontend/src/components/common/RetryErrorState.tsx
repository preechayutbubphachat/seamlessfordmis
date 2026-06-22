type RetryErrorStateProps = {
  title: string;
  detail: string;
  onRetry?: () => void;
  retryLabel?: string;
};

export function RetryErrorState({
  title,
  detail,
  onRetry,
  retryLabel = "ลองใหม่อีกครั้ง",
}: RetryErrorStateProps) {
  return (
    <section className="panel error-panel" aria-live="polite">
      <p className="eyebrow">Error</p>
      <h3>{title}</h3>
      <p className="summary-copy">รายละเอียดข้อผิดพลาด: {detail}</p>
      {onRetry ? (
        <div className="button-row section-block">
          <button className="secondary-button" type="button" onClick={onRetry}>
            {retryLabel}
          </button>
        </div>
      ) : null}
    </section>
  );
}
