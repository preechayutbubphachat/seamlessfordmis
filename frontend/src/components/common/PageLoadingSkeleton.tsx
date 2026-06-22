type PageLoadingSkeletonProps = {
  title?: string;
  message?: string;
  cards?: number;
  rows?: number;
};

export function PageLoadingSkeleton({
  title = "โปรดรอสักครู่...",
  message = "กำลังโหลดข้อมูล...",
  cards = 3,
  rows = 5,
}: PageLoadingSkeletonProps) {
  return (
    <div className="stack-layout" aria-live="polite">
      <section className="panel">
        <div className="loading-state">
          <span className="loading-spinner" aria-hidden="true" />
          <div>
            <p className="eyebrow">Loading</p>
            <h3>{title}</h3>
            <p className="summary-copy">{message}</p>
          </div>
        </div>
      </section>

      <section className="panel">
        <div className="summary-grid">
          {Array.from({ length: cards }).map((_, index) => (
            <div key={`card-${index}`} className="summary-card default">
              <div className="skeleton-line short" />
              <div className="skeleton-line medium" />
              <div className="skeleton-line short" />
            </div>
          ))}
        </div>
      </section>

      <section className="panel">
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>ข้อมูล</th>
                <th>สถานะ</th>
                <th>รายละเอียด</th>
              </tr>
            </thead>
            <tbody>
              {Array.from({ length: rows }).map((_, index) => (
                <tr key={`row-${index}`}>
                  <td><div className="skeleton-line medium" /></td>
                  <td><div className="skeleton-line short" /></td>
                  <td><div className="skeleton-line long" /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
