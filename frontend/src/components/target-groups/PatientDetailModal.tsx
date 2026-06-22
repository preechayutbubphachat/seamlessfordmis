"use client";

import { useEffect, useState } from "react";

import { getApiErrorMessage, getResultSourceHistory } from "@/lib/api";
import { formatAgeDisplay, formatDate, formatNumber, formatSexLabel } from "@/lib/format";
import type { ResultSourceHistory } from "@/types/patient";
import type { GroupResultRow } from "@/types/result";
import { getResultCategoryLabel } from "./ResultCategoryBadge";

type ModalTab = "summary" | "provenance" | "history" | "followup" | "correction";

const TABS: { id: ModalTab; label: string }[] = [
  { id: "summary", label: "ข้อมูลสรุป" },
  { id: "provenance", label: "ที่มาข้อมูล" },
  { id: "history", label: "ประวัติการตรวจ" },
  { id: "followup", label: "ติดตามผล" },
  { id: "correction", label: "แก้ไขข้อมูล" },
];

function getMatchMethodLabel(method: string | null) {
  switch (method) {
    case "identifier_exact":
      return "ตรงจากเลขตัวระบุ";
    case "name_exact_secondary":
      return "ตรงจากชื่อ (สำรอง)";
    case "needs_review":
      return "ต้องตรวจสอบ";
    case "not_found":
      return "ไม่พบข้อมูล";
    default:
      return "-";
  }
}

function getHistorySourceLabel(summary: string) {
  switch (summary) {
    case "screening_db_only":
      return "ฐานข้อมูลการตรวจโรค";
    case "target_group_file_only":
      return "ไฟล์กลุ่มเป้าหมาย";
    case "both_sources":
      return "ทั้งสองแหล่ง";
    case "no_history_found":
      return "ยังไม่พบประวัติ";
    default:
      return summary;
  }
}

function getEventSourceLabel(sourceType: string | null) {
  switch (sourceType) {
    case "target_group_history_sheet":
      return "sheet ประวัติในไฟล์กลุ่มเป้าหมาย";
    case "target_group_roster_context":
      return "บริบทประวัติที่ฝังอยู่ใน roster";
    default:
      return "-";
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

// ── Tab: ข้อมูลสรุป ──────────────────────────────────────────────────────────
function TabSummary({ row }: { row: GroupResultRow }) {
  return (
    <div className="modal-grid section-block">
      <section className="subtle-box">
        <h4>ข้อมูลผู้รับบริการ</h4>
        <div className="key-grid">
          <div>
            <dt>CID / ตัวระบุ</dt>
            <dd>{row.normalized_cid ?? row.matched_identifier ?? "-"}</dd>
          </div>
          <div>
            <dt>เพศ</dt>
            <dd>{formatSexLabel(row.sex)}</dd>
          </div>
          <div>
            <dt>อายุ</dt>
            <dd>{formatAgeDisplay({ age: row.age, rawAge: row.raw_age, birthDate: row.birth_date })}</dd>
          </div>
          <div>
            <dt>หมวดผลลัพธ์</dt>
            <dd>{getResultCategoryLabel(row.result_category)}</dd>
          </div>
          <div>
            <dt>แหล่งหลักฐาน</dt>
            <dd>{getHistorySourceLabel(row.history_source_summary)}</dd>
          </div>
          <div>
            <dt>วิธีจับคู่ฐานโรค</dt>
            <dd>{getMatchMethodLabel(row.match_method)}</dd>
          </div>
          <div>
            <dt>สถานะการรวมบุคคล</dt>
            <dd>{getPersonLinkLabel(row.person_link_status)}</dd>
          </div>
          <div>
            <dt>ความเชื่อมั่น</dt>
            <dd>{row.match_confidence ?? "-"}</dd>
          </div>
          <div>
            <dt>สัญชาติจากไฟล์กลุ่มเป้าหมาย</dt>
            <dd>{row.target_group_nationality ?? "-"}</dd>
          </div>
          <div>
            <dt>ที่อยู่จากไฟล์กลุ่มเป้าหมาย</dt>
            <dd>{row.target_group_address ?? "-"}</dd>
          </div>
          <div className="full-span">
            <dt>เหตุผลการรวมข้อมูล</dt>
            <dd>{row.duplicate_reason ?? "-"}</dd>
          </div>
        </div>
      </section>

      <section className="subtle-box">
        <h4>สรุปประวัติที่ใช้ในผลลัพธ์</h4>
        <div className="key-grid">
          <div>
            <dt>พบในฐานข้อมูลการตรวจโรค</dt>
            <dd>{row.history_found_in_screening_db ? "พบ" : "ไม่พบ"}</dd>
          </div>
          <div>
            <dt>พบในไฟล์กลุ่มเป้าหมาย</dt>
            <dd>{row.history_found_in_target_group_file ? "พบ" : "ไม่พบ"}</dd>
          </div>
          <div>
            <dt>จำนวนประวัติจากฐานข้อมูลการตรวจโรค</dt>
            <dd>{formatNumber(row.screening_db_history_count)}</dd>
          </div>
          <div>
            <dt>จำนวนประวัติจากไฟล์กลุ่มเป้าหมาย</dt>
            <dd>{formatNumber(row.target_group_history_count)}</dd>
          </div>
          <div>
            <dt>จำนวนครั้งที่พบรวม</dt>
            <dd>{formatNumber(row.matching_record_count)}</dd>
          </div>
          <div>
            <dt>วันที่ล่าสุด</dt>
            <dd>{formatDate(row.last_visit_date)}</dd>
          </div>
          <div>
            <dt>ผ่านมากี่วัน</dt>
            <dd>{formatNumber(row.days_since_last_visit)}</dd>
          </div>
          <div>
            <dt>ผ่านมากี่ปี</dt>
            <dd>
              {row.years_since_last_visit !== null && row.years_since_last_visit !== undefined
                ? `${formatNumber(row.years_since_last_visit)} ปี`
                : "-"}
            </dd>
          </div>
          <div>
            <dt>ไฟล์หลัก</dt>
            <dd>{row.source_file_name ?? "-"}</dd>
          </div>
          <div>
            <dt>sheet หลัก</dt>
            <dd>{row.source_sheet_name ?? "-"}</dd>
          </div>
        </div>
      </section>
    </div>
  );
}

// ── Tab: ที่มาข้อมูล (Provenance) ────────────────────────────────────────────
function TabProvenance({ row }: { row: GroupResultRow }) {
  return (
    <section className="subtle-box section-block">
      <h4>Provenance ของแถวต้นทางที่ถูกรวม</h4>
      <p className="summary-copy">รวมผลลัพธ์แบบ 1 คนต่อ 1 แถว พร้อม provenance ของทุกแถวต้นทางที่ถูกรวมเข้ามา</p>
      {row.provenance_details.length ? (
        <div className="table-wrap section-block">
          <table className="data-table">
            <thead>
              <tr>
                <th>ไฟล์ต้นทาง</th>
                <th>sheet</th>
                <th>แถวต้นทาง</th>
                <th>วิธีจับคู่</th>
                <th>สถานะ</th>
                <th>หมายเหตุ</th>
              </tr>
            </thead>
            <tbody>
              {row.provenance_details.map((item, index) => (
                <tr
                  key={`${item.source_file_name ?? "file"}-${item.source_sheet_name ?? "sheet"}-${item.source_row_no ?? item.row_no ?? index}`}
                >
                  <td>{item.source_file_name ?? "-"}</td>
                  <td>{item.source_sheet_name ?? "-"}</td>
                  <td>{item.source_row_no ?? item.row_no ?? "-"}</td>
                  <td>{getMatchMethodLabel(item.match_method ?? null)}</td>
                  <td>{item.match_status ?? "-"}</td>
                  <td>{item.warning_message ?? item.error_message ?? "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="summary-copy">ไม่มี provenance เพิ่มเติมนอกเหนือจากแถวหลัก</p>
      )}

      {/* Original source context from target group file */}
      {row.source_origin_context ? (
        <div className="subtle-box section-block">
          <h5>บริบทต้นทางจากไฟล์กลุ่มเป้าหมาย</h5>
          <p className="summary-copy">{row.source_origin_context}</p>
        </div>
      ) : null}
    </section>
  );
}

// ── Tab: ประวัติการตรวจ ───────────────────────────────────────────────────────
function TabHistory({
  row,
  loading,
  error,
  sourceHistory,
}: {
  row: GroupResultRow;
  loading: boolean;
  error: string | null;
  sourceHistory: ResultSourceHistory | null;
}) {
  return (
    <div className="section-block">
      {/* Target group history */}
      <section className="subtle-box">
        <h4>ประวัติจากไฟล์กลุ่มเป้าหมาย</h4>
        {loading ? (
          <p className="summary-copy">กำลังโหลดประวัติ...</p>
        ) : error ? (
          <p className="feedback-line is-error">{error}</p>
        ) : sourceHistory && sourceHistory.target_group_history_events.length > 0 ? (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>วันที่</th>
                  <th>บริการ/วิธีตรวจ</th>
                  <th>ผล</th>
                  <th>ชนิดแหล่งข้อมูล</th>
                  <th>ที่มา</th>
                </tr>
              </thead>
              <tbody>
                {sourceHistory.target_group_history_events.map((item, index) => (
                  <tr key={`tg-${item.source_file_name ?? "file"}-${item.source_sheet_name ?? "sheet"}-${item.source_row_no ?? index}`}>
                    <td>{formatDate(item.visit_date)}</td>
                    <td>{item.raw_service_type ?? item.normalized_service_key ?? "-"}</td>
                    <td>{item.raw_result ?? "-"}</td>
                    <td>{getEventSourceLabel(item.source_type)}</td>
                    <td>
                      {[item.source_file_name, item.source_sheet_name, item.source_row_no ? `แถว ${item.source_row_no}` : null]
                        .filter(Boolean)
                        .join(" • ")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="summary-copy">ยังไม่พบประวัติจากไฟล์กลุ่มเป้าหมาย</p>
        )}
        {row.target_group_history_note ? (
          <p className="summary-copy section-block">หมายเหตุจากไฟล์กลุ่มเป้าหมาย: {row.target_group_history_note}</p>
        ) : null}
      </section>

      {/* Screening database history */}
      <section className="subtle-box section-block">
        <h4>ประวัติจากฐานข้อมูลการตรวจโรค</h4>
        {loading ? (
          <p className="summary-copy">กำลังโหลดประวัติการตรวจ...</p>
        ) : error ? (
          <p className="feedback-line is-error">{error}</p>
        ) : sourceHistory && sourceHistory.screening_db_records.length > 0 ? (
          <>
            <p className="summary-copy">
              พบ {sourceHistory.screening_db_records.length} รายการ
              {sourceHistory.full_name ? ` สำหรับ ${sourceHistory.full_name}` : null}
            </p>
            <div className="table-wrap section-block">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>วันที่</th>
                    <th>ประเภทบริการ</th>
                    <th>service key</th>
                    <th>ไฟล์ต้นทาง</th>
                    <th>แถวต้นทาง</th>
                  </tr>
                </thead>
                <tbody>
                  {sourceHistory.screening_db_records.map((item) => (
                    <tr key={item.record_id}>
                      <td>{formatDate(item.visit_date)}</td>
                      <td>{item.raw_service_type}</td>
                      <td>{item.normalized_service_key}</td>
                      <td>{item.source_file_name ?? "-"}</td>
                      <td>{item.source_row_no ?? "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        ) : (
          <p className="summary-copy">
            {sourceHistory
              ? "ไม่พบประวัติจากฐานข้อมูลการตรวจโรคสำหรับบริการที่เลือก"
              : loading
                ? "กำลังโหลด..."
                : "ยังไม่ได้โหลดข้อมูล"}
          </p>
        )}
      </section>
    </div>
  );
}

// ── Tab: ติดตามผล ─────────────────────────────────────────────────────────────
const FOLLOWUP_STATUSES = [
  { value: "not_contacted", label: "ยังไม่ติดต่อ" },
  { value: "contacted", label: "ติดต่อแล้ว" },
  { value: "appointment_made", label: "นัดหมายแล้ว" },
  { value: "completed", label: "ดำเนินการแล้ว" },
  { value: "cancelled", label: "ยกเลิก" },
  { value: "not_found", label: "ไม่พบตัว" },
] as const;

function TabFollowUp({ row }: { row: GroupResultRow }) {
  return (
    <div className="section-block">
      <div className="api-stub-box api-stub-compact">
        <span className="api-stub-icon-sm">📋</span>
        <div>
          <strong>ระบบบันทึกการติดตามผลอยู่ระหว่างพัฒนา</strong>
          <p className="summary-copy">
            API:{" "}
            <code>POST /target-groups/[group_id]/results/[result_id]/rows/[row_id]/followups</code>
          </p>
        </div>
      </div>
      <form className="followup-form" onSubmit={(e) => e.preventDefault()}>
        <fieldset disabled className="followup-fieldset">
          <legend className="followup-legend">
            บันทึกการติดตามผล — {row.full_name ?? "ผู้รับบริการ"}
          </legend>
          <div className="form-grid-2">
            <label className="form-field">
              <span className="form-field-label">สถานะการติดตาม *</span>
              <select>
                {FOLLOWUP_STATUSES.map((s) => (
                  <option key={s.value} value={s.value}>
                    {s.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="form-field">
              <span className="form-field-label">วันที่ติดตาม</span>
              <input type="date" />
            </label>
            <label className="form-field">
              <span className="form-field-label">ผู้ติดตาม</span>
              <input type="text" placeholder="ชื่อเจ้าหน้าที่" />
            </label>
            <label className="form-field">
              <span className="form-field-label">วันนัดถัดไป</span>
              <input type="date" />
            </label>
          </div>
          <label className="form-field">
            <span className="form-field-label">ผลการติดตาม</span>
            <input type="text" placeholder="สรุปผลการติดตาม" />
          </label>
          <label className="form-field">
            <span className="form-field-label">หมายเหตุ</span>
            <textarea rows={3} placeholder="รายละเอียดเพิ่มเติม" />
          </label>
        </fieldset>
        <div className="button-row">
          <button
            type="submit"
            className="primary-button compact-button"
            disabled
            title="ระบบบันทึกการติดตามผลอยู่ระหว่างพัฒนา"
          >
            บันทึกการติดตามผล
          </button>
          <span className="summary-copy">ฟิลด์ทั้งหมดยังไม่ถูกบันทึก — API ยังไม่พร้อม</span>
        </div>
      </form>
    </div>
  );
}

// ── Tab: แก้ไขข้อมูล ─────────────────────────────────────────────────────────
function TabCorrection({ row }: { row: GroupResultRow }) {
  return (
    <div className="section-block">
      <div className="api-stub-box api-stub-compact">
        <span className="api-stub-icon-sm">✏️</span>
        <div>
          <strong>ระบบแก้ไขข้อมูลอยู่ระหว่างพัฒนา</strong>
          <p className="summary-copy">
            บันทึก overlay/correction แยกต่างหาก — ไม่เขียนทับข้อมูลต้นทาง
          </p>
          <p className="summary-copy">
            API:{" "}
            <code>GET/POST /target-groups/[group_id]/results/[result_id]/rows/[row_id]/corrections</code>
          </p>
        </div>
      </div>
      <form className="followup-form" onSubmit={(e) => e.preventDefault()}>
        <fieldset disabled className="followup-fieldset">
          <legend className="followup-legend">
            แก้ไขข้อมูล — {row.full_name ?? "ผู้รับบริการ"}
          </legend>

          <p className="form-section-title">ฟิลด์ระบุตัวตน</p>
          <div className="api-stub-warning" style={{ marginBottom: "0.75rem" }}>
            <strong>⚠ ข้อควรระวัง:</strong> การแก้ไข CID, ชื่อ หรือวันเกิดจะตั้งค่า{" "}
            <code>review_required = true</code> โดยอัตโนมัติ และต้องผ่านการยืนยัน
          </div>
          <div className="form-grid-2">
            <label className="form-field">
              <span className="form-field-label">CID / ตัวระบุ</span>
              <input
                type="text"
                defaultValue={row.normalized_cid ?? row.matched_identifier ?? ""}
                placeholder="รหัสบัตรประชาชน"
              />
            </label>
            <label className="form-field">
              <span className="form-field-label">วันเกิด</span>
              <input type="date" defaultValue={row.birth_date ?? ""} />
            </label>
            <label className="form-field" style={{ gridColumn: "1 / -1" }}>
              <span className="form-field-label">ชื่อ-สกุล</span>
              <input
                type="text"
                defaultValue={row.full_name ?? ""}
                placeholder="ชื่อ นามสกุล"
              />
            </label>
          </div>

          <p className="form-section-title">ฟิลด์ทั่วไป</p>
          <div className="form-grid-2">
            <label className="form-field">
              <span className="form-field-label">เพศ</span>
              <select defaultValue={row.sex ?? ""}>
                <option value="">— ไม่ระบุ —</option>
                <option value="male">ชาย</option>
                <option value="female">หญิง</option>
                <option value="other">อื่น ๆ</option>
              </select>
            </label>
            <label className="form-field">
              <span className="form-field-label">สัญชาติ</span>
              <input
                type="text"
                defaultValue={row.target_group_nationality ?? ""}
                placeholder="สัญชาติ"
              />
            </label>
            <label className="form-field" style={{ gridColumn: "1 / -1" }}>
              <span className="form-field-label">ที่อยู่</span>
              <input
                type="text"
                defaultValue={row.target_group_address ?? ""}
                placeholder="ที่อยู่"
              />
            </label>
          </div>

          <label className="form-field">
            <span className="form-field-label">เหตุผลการแก้ไข *</span>
            <textarea rows={2} placeholder="ระบุเหตุผลที่แก้ไข — บังคับกรอก" />
          </label>
        </fieldset>
        <div className="button-row">
          <button
            type="submit"
            className="primary-button compact-button"
            disabled
            title="ระบบแก้ไขข้อมูลอยู่ระหว่างพัฒนา"
          >
            บันทึกการแก้ไข
          </button>
          <span className="summary-copy">ฟิลด์ทั้งหมดยังไม่ถูกบันทึก — API ยังไม่พร้อม</span>
        </div>
      </form>
    </div>
  );
}

// ── Main modal ────────────────────────────────────────────────────────────────
export function PatientDetailModal({
  row,
  groupId,
  selectedServiceKeys,
  onClose,
}: {
  row: GroupResultRow | null;
  groupId: string;
  selectedServiceKeys: string[];
  onClose: () => void;
}) {
  const [activeTab, setActiveTab] = useState<ModalTab>("summary");
  const [sourceHistory, setSourceHistory] = useState<ResultSourceHistory | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Reset tab to summary whenever a new row is opened
  useEffect(() => {
    if (row) setActiveTab("summary");
    else {
      setSourceHistory(null);
      setError(null);
    }
  }, [row?.result_id]); // eslint-disable-line react-hooks/exhaustive-deps

  // Keyboard close
  useEffect(() => {
    if (!row) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [row, onClose]);

  // Load source history when history tab is first activated
  useEffect(() => {
    if (activeTab !== "history" || !row) return;

    let cancelled = false;

    async function loadSourceHistory() {
      if (!row) return;
      setLoading(true);
      setError(null);
      try {
        const response = await getResultSourceHistory(groupId, row.result_id, selectedServiceKeys);
        if (!cancelled) setSourceHistory(response);
      } catch (fetchError) {
        if (!cancelled) setError(getApiErrorMessage(fetchError, "โหลดประวัติหลักฐานไม่สำเร็จ"));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void loadSourceHistory();
    return () => { cancelled = true; };
  }, [activeTab, row?.result_id, groupId, selectedServiceKeys]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!row) return null;

  return (
    <div
      className="modal-backdrop"
      role="dialog"
      aria-modal="true"
      aria-labelledby="patient-detail-title"
      onClick={onClose}
    >
      <div className="modal-card modal-card-wide" onClick={(event) => event.stopPropagation()}>
        {/* Header */}
        <div className="panel-head">
          <div>
            <p className="eyebrow">รายละเอียดรายบุคคล</p>
            <h3 id="patient-detail-title">{row.full_name ?? "ไม่พบชื่อผู้รับบริการ"}</h3>
            {row.review_required ? (
              <span className="badge is-warning" title="แถวนี้ต้องตรวจสอบตัวตนก่อนรวมข้อมูล">
                ⚠ ต้องตรวจสอบตัวตน
              </span>
            ) : null}
          </div>
          <button className="secondary-button compact-button" type="button" onClick={onClose}>
            ปิด
          </button>
        </div>

        {/* Tab navigation */}
        <div className="modal-tabs" role="tablist">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              role="tab"
              aria-selected={activeTab === tab.id}
              className={`modal-tab${activeTab === tab.id ? " active" : ""}`}
              type="button"
              onClick={() => setActiveTab(tab.id)}
            >
              {tab.label}
              {tab.id === "followup" || tab.id === "correction" ? (
                <span className="modal-tab-stub-dot" title="อยู่ระหว่างพัฒนา"> 🚧</span>
              ) : null}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div className="modal-tab-body">
          {activeTab === "summary" && <TabSummary row={row} />}
          {activeTab === "provenance" && <TabProvenance row={row} />}
          {activeTab === "history" && (
            <TabHistory
              row={row}
              loading={loading}
              error={error}
              sourceHistory={sourceHistory}
            />
          )}
          {activeTab === "followup" && <TabFollowUp row={row} />}
          {activeTab === "correction" && <TabCorrection row={row} />}
        </div>

        {/* Evidence / warning footer.
            Target-group-file history is VALID evidence — render it as an info box,
            not a red error. Keep the raw technical note (incl. duplicate-CID merge
            provenance) visible but de-emphasized. Only show the red error style
            when there is a warning AND no valid target-group-file evidence. */}
        {row.history_found_in_target_group_file ? (
          <div className="subtle-box section-block">
            <span className="status-chip ready">{"พบประวัติจากไฟล์กลุ่มเป้าหมาย"}</span>
            <p className="summary-copy" style={{ marginTop: "8px" }}>
              {row.history_found_in_screening_db
                ? "พบประวัติทั้งในฐานข้อมูลการตรวจโรคและไฟล์กลุ่มเป้าหมาย ระบบเก็บ provenance ทุกแหล่งไว้ตรวจสอบย้อนหลัง"
                : "ไม่พบในฐานข้อมูลการตรวจโรค แต่พบประวัติในไฟล์กลุ่มเป้าหมาย ระบบจึงใช้ข้อมูลนี้เป็นหลักฐาน พร้อมเก็บ provenance ไว้ตรวจสอบย้อนหลัง"}
            </p>
            {row.warning_message ? (
              <p className="table-secondary-text" style={{ marginTop: "6px" }}>
                {"รายละเอียดเชิงเทคนิค: " + row.warning_message}
              </p>
            ) : null}
          </div>
        ) : row.warning_message ? (
          <p className="feedback-line is-error section-block">{row.warning_message}</p>
        ) : null}
      </div>
    </div>
  );
}
