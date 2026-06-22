import { DashboardLivePanel } from "@/components/dashboard-live-panel";
import { Shell } from "@/components/shell";
import { StatusCard } from "@/components/status-card";
import { getSystemStatus } from "@/lib/api";

export default async function DashboardPage() {
  const status = await getSystemStatus();

  return (
    <Shell>
      <div className="stack-lg">
        <section className="hero stack-md">
          <p className="eyebrow">สถานะข้อมูลหลัก</p>
          <h2>ระบบค้นหาจะพร้อมใช้งานเมื่อยืนยันชุดข้อมูล Excel ล่าสุดแล้วเท่านั้น</h2>
          <p className="muted">
            ใช้ SHA-256 เป็นหลักฐานอ้างอิงหลัก และยังแสดงชื่อไฟล์ ขนาด และเวลาแก้ไขเพื่อการตรวจสอบย้อนหลัง
          </p>
        </section>

        <section className="dashboard-grid">
          <StatusCard
            label="ความพร้อมของฐานข้อมูล"
            value={status?.dataset_ready ? "พร้อมใช้งาน" : "ยังไม่พร้อม"}
            tone={status?.dataset_ready ? "success" : "warning"}
            helper="หน้าค้นหาควรถูกล็อกไว้จนกว่าชุดข้อมูลหลักจะพร้อม"
          />
          <StatusCard
            label="การเปลี่ยนแปลงไฟล์ต้นทาง"
            value={status?.source_file_changed ? "มีการเปลี่ยนแปลง" : "ไม่เปลี่ยนแปลง"}
            tone={status?.source_file_changed ? "warning" : "success"}
            helper="เทียบ manifest hash ของไฟล์ชุดปัจจุบันกับงานนำเข้าล่าสุด"
          />
          <StatusCard
            label="จำนวนผู้ป่วย"
            value={String(status?.row_counts.patients ?? 0)}
            helper="จำนวนผู้ป่วยในฐานข้อมูลใช้งานปัจจุบัน"
          />
          <StatusCard
            label="จำนวนประวัติการรักษา"
            value={String(status?.row_counts.diagnosis_history ?? 0)}
            helper="จำนวนแถวประวัติการตรวจหรือรักษาในฐานข้อมูลปัจจุบัน"
          />
          <StatusCard
            label="จำนวนไฟล์ต้นทาง"
            value={String(status?.source_file_count ?? 0)}
            helper="จำนวน workbook ใน batch ที่ใช้งานอยู่"
          />
        </section>

        <DashboardLivePanel initialStatus={status} />

        <section className="panel stack-md">
          <div>
            <p className="panel-label">ข้อมูลงานนำเข้าล่าสุด</p>
            <h2>{status?.import_status ?? "ยังไม่มีงานนำเข้าที่เสร็จสมบูรณ์"}</h2>
          </div>
          <div className="stats-grid">
            <div>
              <p className="panel-label">งานนำเข้า</p>
              <strong>{status?.last_completed_import_job_id ?? "-"}</strong>
            </div>
            <div>
              <p className="panel-label">ไฟล์ตัวแทน</p>
              <strong>{status?.fingerprint?.filename ?? "ไม่พบ"}</strong>
            </div>
            <div>
              <p className="panel-label">Manifest hash</p>
              <strong>{status?.manifest_hash_sha256?.slice(0, 16) ?? "-"}</strong>
            </div>
          </div>
          <div className="table-wrap">
            <table>
              <tbody>
                <tr>
                  <th>Batch manifest hash</th>
                  <td>{status?.manifest_hash_sha256 ?? "ไม่มีข้อมูล"}</td>
                </tr>
                <tr>
                  <th>File hash ของไฟล์ตัวแทน</th>
                  <td>{status?.fingerprint?.sha256 ?? "ไม่มีข้อมูล"}</td>
                </tr>
                <tr>
                  <th>เวลาแก้ไขล่าสุด</th>
                  <td>{status?.fingerprint?.modified_at ?? "ไม่มีข้อมูล"}</td>
                </tr>
                <tr>
                  <th>ขนาดไฟล์ (bytes)</th>
                  <td>{status?.fingerprint?.size_bytes ?? "ไม่มีข้อมูล"}</td>
                </tr>
                <tr>
                  <th>พาธไฟล์</th>
                  <td>{status?.fingerprint?.path ?? "ไม่มีข้อมูล"}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </Shell>
  );
}
