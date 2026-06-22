import type { PatientSummary } from "@/types/patient";
import { formatDate } from "@/lib/format";

export function PatientHeader({ patient }: { patient: PatientSummary }) {
  return (
    <section className="panel">
      <p className="eyebrow">Patient profile</p>
      <h3>{patient.full_name}</h3>
      <dl className="key-grid">
        <div>
          <dt>PID</dt>
          <dd>{patient.pid ?? "-"}</dd>
        </div>
        <div>
          <dt>CID</dt>
          <dd>{patient.citizen_id ?? "-"}</dd>
        </div>
        <div>
          <dt>HN</dt>
          <dd>{patient.hn ?? "-"}</dd>
        </div>
        <div>
          <dt>วันเกิด</dt>
          <dd>{formatDate(patient.birth_date)}</dd>
        </div>
      </dl>
    </section>
  );
}
