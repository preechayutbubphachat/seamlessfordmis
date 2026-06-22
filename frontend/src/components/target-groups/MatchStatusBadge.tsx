function getMatchStatusMeta(status: string) {
  switch (status) {
    case "matched":
      return { tone: "ready", label: "พบข้อมูล" };
    case "not_found":
      return { tone: "muted", label: "ไม่พบข้อมูล" };
    case "needs_review":
      return { tone: "warning", label: "ต้องตรวจสอบ" };
    case "ambiguous":
      return { tone: "danger", label: "พบหลายรายการ" };
    case "invalid":
      return { tone: "danger", label: "ตัวระบุไม่ถูกต้อง" };
    case "out_of_scope":
      return { tone: "muted", label: "นอกขอบเขต" };
    default:
      return { tone: "muted", label: status };
  }
}

export function MatchStatusBadge({ status }: { status: string }) {
  const meta = getMatchStatusMeta(status);
  return <span className={`status-chip ${meta.tone}`}>{meta.label}</span>;
}
