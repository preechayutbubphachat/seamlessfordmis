import type { DiagnosisHistoryRow } from "@/types/patient";
import { formatDate } from "@/lib/format";

export function PatientTimeline({ history }: { history: DiagnosisHistoryRow[] }) {
  return (
    <section className="panel">
      <p className="eyebrow">Timeline</p>
      <h3>ประวัติการรักษา</h3>
      <div className="timeline">
        {history.length ? (
          history.map((item, index) => (
            <article key={`${item.visit_date}-${index}`} className="timeline-item">
              <p className="timeline-date">{formatDate(item.visit_date)}</p>
              <h4>{item.diagnosis_name ?? item.normalized_disease_key ?? "-"}</h4>
              <p>{item.diagnosis_code ?? "-"}</p>
              <p>{item.department ?? "-"}</p>
            </article>
          ))
        ) : (
          <p className="summary-copy">ยังไม่พบประวัติการรักษา</p>
        )}
      </div>
    </section>
  );
}
