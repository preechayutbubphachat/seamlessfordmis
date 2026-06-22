import type { SourceCheck } from "@/types/system";

export function ImportSummaryCard({ sourceCheck }: { sourceCheck: SourceCheck }) {
  return (
    <section className="panel">
      <p className="eyebrow">Source integrity</p>
      <h3>สรุปไฟล์ต้นทางของฐานข้อมูลการตรวจโรค</h3>
      <p className="summary-copy">{sourceCheck.reason}</p>
      <div className="inline-code-block">
        <span>source-set hash</span>
        <code>{sourceCheck.source_set_hash ?? "-"}</code>
      </div>
      <div className="subtle-box">
        <p>จำนวนไฟล์ต้นทาง: {sourceCheck.source_file_count}</p>
        <p>สถานะการเปลี่ยนแปลง: {sourceCheck.changed ? "ต้องซิงก์ใหม่" : "ชุดไฟล์ล่าสุดตรงกับฐานข้อมูล"}</p>
      </div>
      {sourceCheck.files.length ? (
        <div className="subtle-box">
          <p className="summary-copy">ไฟล์ต้นทางที่ตรวจพบ</p>
          {sourceCheck.files.slice(0, 5).map((file) => (
            <p key={`${file.file_name}-${file.sha256}`}>
              {file.file_name} ({file.file_type}){file.warning_count ? ` • คำเตือน ${file.warning_count}` : ""}
            </p>
          ))}
        </div>
      ) : null}
      {sourceCheck.previous_import ? (
        <div className="subtle-box">
          <p>import ล่าสุด: {String(sourceCheck.previous_import.import_job_id ?? "-")}</p>
          <p>source-set hash ก่อนหน้า: {String(sourceCheck.previous_import.source_set_hash ?? "-")}</p>
        </div>
      ) : null}
    </section>
  );
}
