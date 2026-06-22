type FileTypeRow = {
  ext: string;
  label: string;
  description: string;
  kind: "excel" | "csv" | "pdf" | "other";
  status: "supported" | "staged_only" | "coming_soon";
  statusLabel: string;
};

const FILE_TYPES: FileTypeRow[] = [
  {
    ext: ".xlsx, .xls",
    label: "Excel",
    description: "ไฟล์สเปรดชีต Microsoft Excel",
    kind: "excel",
    status: "supported",
    statusLabel: "รองรับเต็มรูปแบบ",
  },
  {
    ext: ".csv",
    label: "CSV",
    description: "ไฟล์ข้อมูลแบบคั่นด้วยเครื่องหมายจุลภาค",
    kind: "csv",
    status: "supported",
    statusLabel: "รองรับเต็มรูปแบบ",
  },
  {
    ext: ".pdf",
    label: "PDF",
    description: "เอกสาร PDF (ตารางหรือข้อมูล)",
    kind: "pdf",
    status: "staged_only",
    statusLabel: "staged — ต้องตรวจสอบก่อนบันทึก",
  },
  {
    ext: "อื่นๆ",
    label: "อื่นๆ",
    description: "ไฟล์รูปแบบอื่น ๆ ที่ระบบรองรับ",
    kind: "other",
    status: "coming_soon",
    statusLabel: "ยังไม่รองรับ",
  },
];

function statusChipClass(status: FileTypeRow["status"]): string {
  if (status === "supported") return "status-chip ready";
  if (status === "staged_only") return "status-chip warning";
  return "status-chip muted";
}

function FileIcon({ kind }: { kind: FileTypeRow["kind"] }) {
  return (
    <span className={`db-filetype-icon ${kind}`}>
      {kind === "excel" ? "X" : kind === "csv" ? "CSV" : kind === "pdf" ? "PDF" : "DOC"}
    </span>
  );
}

export function SupportedFileTypesCard() {
  return (
    <section className="panel db-middle-card">
      <p className="eyebrow">ไฟล์ที่รองรับ</p>
      <h3>ประเภทไฟล์ที่รองรับ</h3>
      <p className="summary-copy">ระบบสามารถประมวลผลไฟล์ได้หลากหลายรูปแบบ</p>

      <ul className="db-filetype-list">
        {FILE_TYPES.map((ft) => (
          <li key={ft.label} className="db-filetype-row">
            <FileIcon kind={ft.kind} />
            <div className="db-filetype-info">
              <span className="db-filetype-label">
                {ft.label} <span className="db-filetype-ext">({ft.ext})</span>
              </span>
              <span className="db-filetype-desc">{ft.description}</span>
            </div>
            <span className={statusChipClass(ft.status)}>
              {ft.statusLabel}
            </span>
          </li>
        ))}
      </ul>

      <div className="subtle-box db-filetype-note">
        <p>
          ขนาดไฟล์สูงสุดต่อไฟล์: <strong>200 MB</strong>
        </p>
        <p>PDF ที่อัปโหลดจะถูก staged ไว้และต้องผ่านการตรวจสอบก่อน commit เข้าฐานข้อมูล</p>
      </div>
    </section>
  );
}
