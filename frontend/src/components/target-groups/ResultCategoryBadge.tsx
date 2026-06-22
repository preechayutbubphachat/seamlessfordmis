function getResultCategoryMeta(category: string) {
  switch (category) {
    case "screening_db_only":
      return { tone: "ready", label: "พบประวัติในฐานข้อมูลการตรวจโรค" };
    case "target_group_file_only":
      return { tone: "accent", label: "พบประวัติในไฟล์กลุ่มเป้าหมาย" };
    case "both_sources":
      return { tone: "ready", label: "พบประวัติจากทั้งสองแหล่ง" };
    case "no_history_found":
      return { tone: "muted", label: "ยังไม่พบประวัติ" };
    case "invalid_identifier":
      return { tone: "danger", label: "ตัวระบุไม่ถูกต้อง" };
    case "missing_identifier":
      return { tone: "warning", label: "ไม่มีข้อมูลตัวระบุ" };
    case "needs_review":
      return { tone: "warning", label: "ต้องตรวจสอบ" };
    case "review_required_identity":
      return { tone: "warning", label: "ต้องตรวจสอบข้อมูลระบุตัวตน" };
    case "insufficient_identity_data":
      return { tone: "danger", label: "ข้อมูลระบุตัวตนไม่พอ" };
    case "non_thai_nationality":
      return { tone: "accent", label: "ไม่ใช่คนไทย" };
    case "outside_target_scope":
      return { tone: "muted", label: "นอกขอบเขตกลุ่มเป้าหมาย" };
    default:
      return { tone: "muted", label: category };
  }
}

export function getResultCategoryLabel(category: string) {
  return getResultCategoryMeta(category).label;
}

export function ResultCategoryBadge({ category }: { category: string }) {
  const meta = getResultCategoryMeta(category);
  return <span className={`status-chip ${meta.tone}`}>{meta.label}</span>;
}
