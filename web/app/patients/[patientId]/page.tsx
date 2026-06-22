import { Shell } from "@/components/shell";
import { getPatientHistory } from "@/lib/api";

export default async function PatientDetailPage({ params }: { params: Promise<{ patientId: string }> }) {
  const { patientId } = await params;
  let response;

  try {
    response = await getPatientHistory(patientId);
  } catch (error) {
    return (
      <Shell>
        <div className="stack-lg">
          <section className="hero stack-md">
            <p className="eyebrow">รายละเอียดผู้ป่วย</p>
            <h2>ไม่พบผู้ป่วยเลขที่ #{patientId}</h2>
            <p className="muted">กรุณาเปิดจากผลลัพธ์กลุ่มเป้าหมาย หรือใช้ลิงก์ตัวอย่างในเมนูด้านซ้าย</p>
          </section>
          <section className="panel">
            <p className="error-text">{error instanceof Error ? error.message : "ไม่สามารถโหลดประวัติผู้ป่วยได้"}</p>
          </section>
        </div>
      </Shell>
    );
  }

  return (
    <Shell>
      <div className="stack-lg">
        <section className="hero stack-md">
          <p className="eyebrow">รายละเอียดผู้ป่วย</p>
          <h2>{response.patient.full_name ?? `Patient #${patientId}`}</h2>
          <p className="muted">
            PID {response.patient.pid ?? "-"} | HN {response.patient.hn ?? "-"} | วันเกิด {response.patient.birth_date ?? "-"}
          </p>
        </section>
        <section className="panel stack-md">
          <p className="panel-label">ลำดับประวัติการตรวจหรือรักษา</p>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>วันที่รับบริการ</th>
                  <th>โรค / รายการบริการ</th>
                  <th>รหัสกลุ่ม</th>
                  <th>รหัสวินิจฉัย</th>
                  <th>สิทธิ / รูปแบบบริการ</th>
                  <th>หน่วยบริการ</th>
                </tr>
              </thead>
              <tbody>
                {response.history.map((item, index) => (
                  <tr key={`${item.visit_date}-${item.normalized_disease_key}-${index}`}>
                    <td>{item.visit_date ?? "-"}</td>
                    <td>{item.disease_name_raw ?? "-"}</td>
                    <td>{item.normalized_disease_key ?? "-"}</td>
                    <td>{item.diagnosis_code ?? "-"}</td>
                    <td>{item.encounter_type ?? "-"}</td>
                    <td>{item.provider_name ?? "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </Shell>
  );
}
