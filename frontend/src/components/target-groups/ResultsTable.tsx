import { formatAgeDisplay, formatDate, formatNumber, formatSexLabel } from "@/lib/format";
import type { GroupResultRow } from "@/types/result";
import { MatchStatusBadge } from "./MatchStatusBadge";
import { ResultCategoryBadge } from "./ResultCategoryBadge";

// ─────────────────────────────────────────────────────────
// Column definitions
// ─────────────────────────────────────────────────────────

/** Keys that map to hideable columns. "cid", "name", "status", "result", "actions" are always visible. */
export type HideableCol =
  | "age"
  | "sex"
  | "match_count"
  | "last_visit"
  | "days_since"
  | "provenance";

/** Keys that the backend can sort by (must match _SORTABLE_COLUMNS in result_generation_service.py). */
export type SortableCol =
  | "full_name"
  | "age"
  | "last_visit_date"
  | "days_since_last_visit"
  | "years_since_last_visit"
  | "screening_status"
  | "matching_record_count";

// ─────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────

function getScreeningStatusMeta(status: string) {
  switch (status) {
    case "never_checked":
      return { tone: "muted", label: "ยังไม่เคยตรวจ" };
    case "checked_but_overdue":
      return { tone: "warning", label: "ตรวจแล้วแต่เกินกำหนด" };
    case "checked_and_within_threshold":
      return { tone: "ready", label: "ตรวจแล้วและยังไม่เกินกำหนด" };
    case "invalid_identifier":
      return { tone: "danger", label: "ตัวระบุไม่ถูกต้อง" };
    case "missing_identifier":
      return { tone: "warning", label: "ไม่มีข้อมูลตัวระบุ" };
    case "review_required_identity":
      return { tone: "warning", label: "ต้องตรวจสอบตัวตน" };
    case "insufficient_identity_data":
      return { tone: "danger", label: "ข้อมูลตัวตนไม่พอ" };
    case "non_thai_nationality":
      return { tone: "accent", label: "ไม่ใช่คนไทย" };
    case "outside_target_scope":
      return { tone: "muted", label: "นอกขอบเขต" };
    case "needs_review":
      return { tone: "warning", label: "ต้องตรวจสอบ" };
    default:
      return { tone: "muted", label: status };
  }
}

function getPersonLinkLabel(status: string | null) {
  switch (status) {
    case "citizen_id_exact":
      return "รวมด้วย CID ตรงกัน";
    case "name_birthdate_exact":
      return "รวมด้วยชื่อและวันเกิดตรงกัน";
    case "name_birthdate_address_secondary":
      return "รวมด้วยชื่อและที่อยู่ ต้องตรวจสอบ";
    case "review_required":
      return "ข้อมูลระบุตัวตนยังไม่พอ ต้องตรวจสอบ";
    case "insufficient_identity_data":
      return "ข้อมูลระบุตัวตนไม่พอ";
    default:
      return "-";
  }
}

type ProvBadge = { label: string; tone: string; title?: string };

function buildProvenanceBadges(row: GroupResultRow): ProvBadge[] {
  const badges: ProvBadge[] = [];

  if (row.review_required) {
    badges.push({ label: "⚠ ต้องตรวจสอบตัวตน", tone: "warning", title: "แถวนี้ต้องตรวจสอบตัวตนก่อนรวมข้อมูล" });
  }
  if (row.screening_status === "invalid_identifier") {
    badges.push({ label: "CID ไม่ถูกต้อง", tone: "danger" });
  }
  if (row.screening_status === "missing_identifier") {
    badges.push({ label: "ไม่มี CID", tone: "warning" });
  }
  if (row.screening_status === "insufficient_identity_data") {
    badges.push({ label: "ตัวตนไม่พอ", tone: "danger" });
  }

  switch (row.history_source_summary) {
    case "both_sources":
      badges.push({ label: "ทั้งสองแหล่ง", tone: "ready", title: "พบประวัติจากทั้งฐานข้อมูลการตรวจโรคและไฟล์กลุ่มเป้าหมาย" });
      break;
    case "screening_db_only":
      badges.push({ label: "พบจากฐานตรวจโรค", tone: "accent" });
      break;
    case "target_group_file_only":
      badges.push({ label: "พบจากไฟล์กลุ่มเป้าหมาย", tone: "accent" });
      break;
    case "no_history_found":
      badges.push({ label: "ยังไม่พบประวัติ", tone: "muted" });
      break;
  }

  if (row.match_method === "name_exact_secondary") {
    badges.push({ label: "ใช้ชื่อเป็นหลัก ⚠", tone: "warning", title: "จับคู่ด้วยชื่อ ไม่ใช่ CID — ควรตรวจสอบ" });
  }

  if (row.provenance_summary_count > 1) {
    badges.push({ label: `provenance ${row.provenance_summary_count} แถว`, tone: "muted", title: "รวมข้อมูลจากหลายแถวต้นทาง" });
  }

  if (row.warning_message) {
    badges.push({ label: "มีคำเตือน ⚠", tone: "warning", title: row.warning_message });
  }

  return badges;
}

/** Render a sortable <th> with directional indicator. */
function SortTh({
  col,
  label,
  sortCol,
  sortDir,
  onSort,
}: {
  col: SortableCol;
  label: string;
  sortCol?: string | null;
  sortDir?: "asc" | "desc" | null;
  onSort?: (col: string) => void;
}) {
  const isActive = sortCol === col;
  const arrow = isActive ? (sortDir === "desc" ? " ↓" : " ↑") : "";
  return (
    <th
      className={`sortable-th${isActive ? " sort-active" : ""}`}
      onClick={() => onSort?.(col)}
      title={`เรียงตาม${label}`}
      style={{ cursor: onSort ? "pointer" : undefined, userSelect: "none" }}
    >
      {label}{arrow}
    </th>
  );
}

// ─────────────────────────────────────────────────────────
// Main component
// ─────────────────────────────────────────────────────────

export function ResultsTable({
  rows,
  onOpenDetails,
  onFollowUp,
  sortCol,
  sortDir,
  onSort,
  hiddenCols,
}: {
  rows: GroupResultRow[];
  onOpenDetails: (row: GroupResultRow) => void;
  onFollowUp: (row: GroupResultRow) => void;
  /** Active sort column key */
  sortCol?: string | null;
  /** Active sort direction */
  sortDir?: "asc" | "desc" | null;
  /** Called when user clicks a sortable header; receives column key */
  onSort?: (col: string) => void;
  /** Set of HideableCol keys that should be hidden */
  hiddenCols?: Set<string>;
}) {
  const hide = (col: HideableCol) => hiddenCols?.has(col) ?? false;

  if (!rows.length) {
    return <p className="summary-copy">ไม่พบรายการในเงื่อนไขที่เลือก</p>;
  }

  return (
    <div className="table-wrap sticky-table-wrap">
      <table className="data-table sticky-data-table compact-data-table">
        <thead>
          <tr>
            <th>CID / ตัวระบุ</th>
            <SortTh col="full_name" label="ชื่อ-สกุล" sortCol={sortCol} sortDir={sortDir} onSort={onSort} />
            {!hide("age") && (
              <SortTh col="age" label="อายุ" sortCol={sortCol} sortDir={sortDir} onSort={onSort} />
            )}
            {!hide("sex") && <th>เพศ</th>}
            <SortTh col="screening_status" label="สถานะติดตาม" sortCol={sortCol} sortDir={sortDir} onSort={onSort} />
            <th>ผลลัพธ์</th>
            {!hide("match_count") && (
              <SortTh col="matching_record_count" label="จำนวนครั้งที่พบ" sortCol={sortCol} sortDir={sortDir} onSort={onSort} />
            )}
            {!hide("last_visit") && (
              <SortTh col="last_visit_date" label="วันที่ล่าสุด" sortCol={sortCol} sortDir={sortDir} onSort={onSort} />
            )}
            {!hide("days_since") && (
              <SortTh col="days_since_last_visit" label="ผ่านมา (วัน / ปี)" sortCol={sortCol} sortDir={sortDir} onSort={onSort} />
            )}
            {!hide("provenance") && <th>หลักฐาน / ที่มา</th>}
            <th>การดำเนินการ</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const screeningStatus = getScreeningStatusMeta(row.screening_status);
            const provBadges = buildProvenanceBadges(row);

            return (
              <tr key={row.result_id}>
                {/* CID — always visible */}
                <td>
                  <div className="cell-stack compact-cell-stack">
                    <code className="cid-text">{row.normalized_cid ?? row.matched_identifier ?? "-"}</code>
                    {row.matched_identifier && row.matched_identifier !== row.normalized_cid ? (
                      <span className="table-secondary-text">จับคู่ด้วย: {row.matched_identifier}</span>
                    ) : null}
                  </div>
                </td>

                {/* Name — always visible, sortable */}
                <td>
                  <div className="cell-stack compact-cell-stack">
                    <strong>{row.full_name ?? "-"}</strong>
                    {row.person_link_status ? (
                      <span className="table-secondary-text">{getPersonLinkLabel(row.person_link_status)}</span>
                    ) : null}
                  </div>
                </td>

                {/* Age — hideable */}
                {!hide("age") && (
                  <td>{formatAgeDisplay({ age: row.age, rawAge: row.raw_age, birthDate: row.birth_date })}</td>
                )}

                {/* Sex — hideable */}
                {!hide("sex") && <td>{formatSexLabel(row.sex)}</td>}

                {/* Screening status — always visible */}
                <td>
                  <span className={`status-chip ${screeningStatus.tone}`}>{screeningStatus.label}</span>
                </td>

                {/* Result category + match — always visible */}
                <td>
                  <div className="cell-stack compact-cell-stack">
                    <ResultCategoryBadge category={row.result_category} />
                    <MatchStatusBadge status={row.match_status} />
                  </div>
                </td>

                {/* Match count — hideable */}
                {!hide("match_count") && <td>{formatNumber(row.matching_record_count)}</td>}

                {/* Last visit date — hideable */}
                {!hide("last_visit") && <td>{formatDate(row.last_visit_date)}</td>}

                {/* Days/years since — hideable */}
                {!hide("days_since") && (
                  <td>
                    <div className="cell-stack compact-cell-stack">
                      <span>
                        {row.days_since_last_visit !== null && row.days_since_last_visit !== undefined
                          ? `${formatNumber(row.days_since_last_visit)} วัน`
                          : "-"}
                      </span>
                      <span className="table-secondary-text">
                        {row.years_since_last_visit !== null && row.years_since_last_visit !== undefined
                          ? `${formatNumber(row.years_since_last_visit)} ปี`
                          : ""}
                      </span>
                    </div>
                  </td>
                )}

                {/* Provenance badges — hideable */}
                {!hide("provenance") && (
                  <td>
                    {provBadges.length > 0 ? (
                      <div className="prov-badges">
                        {provBadges.map((badge, i) => (
                          <span
                            key={i}
                            className={`prov-badge prov-badge-${badge.tone}`}
                            title={badge.title}
                          >
                            {badge.label}
                          </span>
                        ))}
                      </div>
                    ) : (
                      <span className="table-secondary-text">-</span>
                    )}
                  </td>
                )}

                {/* Actions — always visible */}
                <td>
                  <div className="action-cell">
                    <button
                      className="primary-button compact-button"
                      type="button"
                      disabled
                      title="ระบบบันทึกการติดตามผลอยู่ระหว่างพัฒนา"
                      onClick={() => onFollowUp(row)}
                    >
                      ติดตามผล
                    </button>
                    <button
                      className="secondary-button compact-button"
                      type="button"
                      onClick={() => onOpenDetails(row)}
                    >
                      ดูรายละเอียด
                    </button>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
