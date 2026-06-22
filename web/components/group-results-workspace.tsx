"use client";

import Link from "next/link";
import { useEffect, useMemo, useState, useTransition } from "react";

import {
  confirmTargetGroup,
  exportResults,
  getGroupResults,
  getGroupedDiseaseSummary,
  runMatching
} from "@/lib/api";
import {
  DiseaseOption,
  GroupResultRow,
  GroupedDiseaseSummary,
  MatchRunResponse,
  TargetGroupJob
} from "@/types";

type Props = {
  job: TargetGroupJob;
  diseaseOptions: DiseaseOption[];
  initialResults: GroupResultRow[];
  initialSummary: GroupedDiseaseSummary[];
  initialDiseaseKeys: string[];
};

type FilterMode = "disease" | "service";

const FILTER_MODE_LABELS: Record<FilterMode, string> = {
  disease: "กลุ่มโรค",
  service: "บริการ/การตรวจ"
};

function translateJobStatus(status: string) {
  switch (status) {
    case "uploaded":
      return "อัปโหลดแล้ว";
    case "confirmed":
      return "ยืนยันแล้ว";
    case "matched":
      return "จับคู่แล้ว";
    case "failed":
      return "ล้มเหลว";
    default:
      return status;
  }
}

function translateMatchStatus(status: string) {
  switch (status) {
    case "matched":
      return "พบผู้ป่วย";
    case "needs_review":
      return "ต้องตรวจทาน";
    case "unmatched":
      return "ไม่พบ";
    case "ambiguous":
      return "กำกวม";
    default:
      return status;
  }
}

function translateHistoryValue(value: boolean | null) {
  if (value == null) {
    return "ข้อมูลไม่พอ";
  }
  return value ? "มี" : "ไม่พบ";
}

function pickInitialFilterMode(options: DiseaseOption[], selectedKeys: string[]): FilterMode {
  const selectedOption = options.find((option) => selectedKeys.includes(option.normalized_disease_key));
  return selectedOption?.group_type === "disease" ? "disease" : "service";
}

export function GroupResultsWorkspace({
  job,
  diseaseOptions,
  initialResults,
  initialSummary,
  initialDiseaseKeys
}: Props) {
  const initialMode = pickInitialFilterMode(diseaseOptions, initialDiseaseKeys);
  const [jobState, setJobState] = useState(job);
  const [filterMode, setFilterMode] = useState<FilterMode>(initialMode);
  const [selectedDiseaseKeys, setSelectedDiseaseKeys] = useState(initialDiseaseKeys);
  const [pendingDiseaseKeys, setPendingDiseaseKeys] = useState(initialDiseaseKeys);
  const [results, setResults] = useState(initialResults);
  const [summary, setSummary] = useState(initialSummary);
  const [matchStatus, setMatchStatus] = useState("all");
  const [visitRange, setVisitRange] = useState("all");
  const [matchRun, setMatchRun] = useState<MatchRunResponse | null>(null);
  const [exportMessage, setExportMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  const diseaseModeOptions = useMemo(
    () => diseaseOptions.filter((option) => option.group_type === "disease"),
    [diseaseOptions]
  );
  const serviceModeOptions = useMemo(
    () => diseaseOptions.filter((option) => option.group_type === "service"),
    [diseaseOptions]
  );
  const modeOptions = filterMode === "disease" ? diseaseModeOptions : serviceModeOptions;

  useEffect(() => {
    const nextMode = pickInitialFilterMode(diseaseOptions, initialDiseaseKeys);
    setResults(initialResults);
    setSummary(initialSummary);
    setFilterMode(nextMode);
    setSelectedDiseaseKeys(initialDiseaseKeys);
    setPendingDiseaseKeys(initialDiseaseKeys);
  }, [diseaseOptions, initialDiseaseKeys, initialResults, initialSummary]);

  function refreshDiseaseView(nextDiseaseKeys: string[]) {
    setError(null);
    startTransition(async () => {
      try {
        const [resultResponse, summaryResponse] = await Promise.all([
          getGroupResults(jobState.job_id, nextDiseaseKeys),
          getGroupedDiseaseSummary(jobState.job_id)
        ]);
        setSelectedDiseaseKeys(nextDiseaseKeys);
        setResults(resultResponse.results);
        setSummary(summaryResponse);
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "ไม่สามารถโหลดผลลัพธ์ใหม่ได้");
      }
    });
  }

  function handleFilterModeChange(nextMode: FilterMode) {
    setFilterMode(nextMode);
    const nextOptions = nextMode === "disease" ? diseaseModeOptions : serviceModeOptions;
    const nextSelected = pendingDiseaseKeys.filter((key) =>
      nextOptions.some((option) => option.normalized_disease_key === key)
    );
    setPendingDiseaseKeys(nextSelected.length > 0 ? nextSelected : nextOptions.slice(0, 1).map((option) => option.normalized_disease_key));
  }

  function handleConfirm() {
    setError(null);
    startTransition(async () => {
      try {
        const response = await confirmTargetGroup(jobState.job_id);
        setJobState({ ...jobState, status: response.status });
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "ไม่สามารถยืนยันการนำเข้าได้");
      }
    });
  }

  function handleMatch() {
    setError(null);
    startTransition(async () => {
      try {
        const response = await runMatching(jobState.job_id);
        setMatchRun(response);
        setJobState({ ...jobState, status: response.status, review_rows: response.review_rows });
        refreshDiseaseView(selectedDiseaseKeys);
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "ไม่สามารถจับคู่กลุ่มเป้าหมายได้");
      }
    });
  }

  function handleExport() {
    setError(null);
    setExportMessage(null);
    startTransition(async () => {
      try {
        const response = await exportResults(jobState.job_id);
        setExportMessage(`ส่งออก ${response.row_count} แถวแล้วที่ ${response.export_path}`);
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "ไม่สามารถส่งออกผลลัพธ์ได้");
      }
    });
  }

  const filteredResults = useMemo(() => {
    return results.filter((row) => {
      if (matchStatus !== "all" && row.match_status !== matchStatus) {
        return false;
      }
      if (visitRange === "has-date" && !row.latest_visit_date) {
        return false;
      }
      if (visitRange === "365" && (row.days_since_latest_visit == null || row.days_since_latest_visit > 365)) {
        return false;
      }
      if (visitRange === "180" && (row.days_since_latest_visit == null || row.days_since_latest_visit > 180)) {
        return false;
      }
      return true;
    });
  }, [matchStatus, results, visitRange]);

  const selectedDiseaseLabel = selectedDiseaseKeys
    .map((key) => diseaseOptions.find((option) => option.normalized_disease_key === key)?.disease_group_label ?? key)
    .join(", ");

  const visibleSummary = useMemo(() => {
    const allowedKeys = new Set(modeOptions.map((option) => option.normalized_disease_key));
    return summary.filter((row) => allowedKeys.has(row.disease_key));
  }, [modeOptions, summary]);

  return (
    <div className="stack-lg">
      <section className="panel stack-md">
        <div className="stats-grid">
          <div>
            <p className="panel-label">ชื่อกลุ่ม</p>
            <strong>{jobState.group_name}</strong>
          </div>
          <div>
            <p className="panel-label">สถานะ</p>
            <strong>{translateJobStatus(jobState.status)}</strong>
          </div>
          <div>
            <p className="panel-label">ไฟล์ต้นทาง</p>
            <strong>{jobState.original_filename}</strong>
          </div>
        </div>
        <div className="action-row">
          <button className="button" type="button" disabled={isPending || jobState.status !== "uploaded"} onClick={handleConfirm}>
            ยืนยันการนำเข้า
          </button>
          <button className="button secondary" type="button" disabled={isPending || (jobState.status !== "confirmed" && jobState.status !== "matched")} onClick={handleMatch}>
            เริ่มจับคู่
          </button>
          <button className="button secondary" type="button" disabled={isPending || results.length === 0} onClick={handleExport}>
            ส่งออกผลลัพธ์
          </button>
        </div>
        {matchRun ? (
          <p className="muted">
            จับคู่แล้ว {matchRun.matched_rows} รายการ, ต้องตรวจทาน {matchRun.review_rows} รายการ, ไม่พบ {matchRun.unmatched_rows} รายการ
          </p>
        ) : null}
        {exportMessage ? <p className="muted">{exportMessage}</p> : null}
        {error ? <p className="error-text">{error}</p> : null}
      </section>

      <section className="panel stack-md">
        <div className="action-header">
          <div>
            <p className="panel-label">ตัวกรองผลลัพธ์</p>
            <h2>เลือกมุมมองการค้นหา</h2>
            <p className="muted">สลับระหว่างกลุ่มโรคกับบริการ/การตรวจ เพื่อให้เลือกชุดรายการได้ตรงงานที่ต้องการ</p>
          </div>
          <div className="mode-toggle" role="tablist" aria-label="เลือกโหมดตัวกรอง">
            <button
              className={`toggle-chip ${filterMode === "disease" ? "active" : ""}`}
              type="button"
              onClick={() => handleFilterModeChange("disease")}
            >
              กลุ่มโรค
            </button>
            <button
              className={`toggle-chip ${filterMode === "service" ? "active" : ""}`}
              type="button"
              onClick={() => handleFilterModeChange("service")}
            >
              บริการ/การตรวจ
            </button>
          </div>
        </div>

        <div className="stats-grid">
          <label className="field">
            <span>{FILTER_MODE_LABELS[filterMode]}ที่ต้องการค้นหา</span>
            <select
              multiple
              className="multi-select"
              value={pendingDiseaseKeys}
              onChange={(event) => setPendingDiseaseKeys(Array.from(event.target.selectedOptions, (option) => option.value))}
            >
              {modeOptions.map((option) => (
                <option key={option.normalized_disease_key} value={option.normalized_disease_key}>
                  {option.disease_group_label}
                </option>
              ))}
            </select>
            <small className="muted">กด Ctrl หรือ Command เพื่อเลือกหลายรายการพร้อมกัน</small>
          </label>
          <label className="field">
            <span>สถานะการจับคู่</span>
            <select value={matchStatus} onChange={(event) => setMatchStatus(event.target.value)}>
              <option value="all">ทั้งหมด</option>
              <option value="matched">พบผู้ป่วย</option>
              <option value="needs_review">ต้องตรวจทาน</option>
              <option value="unmatched">ไม่พบ</option>
              <option value="ambiguous">กำกวม</option>
            </select>
          </label>
          <label className="field">
            <span>ช่วงวันที่มารับบริการล่าสุด</span>
            <select value={visitRange} onChange={(event) => setVisitRange(event.target.value)}>
              <option value="all">ทั้งหมด</option>
              <option value="has-date">มีวันที่ล่าสุด</option>
              <option value="180">ภายใน 180 วัน</option>
              <option value="365">ภายใน 365 วัน</option>
            </select>
          </label>
        </div>
        <div className="action-row">
          <button
            className="button secondary"
            type="button"
            disabled={isPending || pendingDiseaseKeys.length === 0}
            onClick={() => refreshDiseaseView(pendingDiseaseKeys)}
          >
            ใช้ตัวกรองนี้
          </button>
        </div>
        <p className="muted">รายการที่เลือกอยู่: {selectedDiseaseLabel || "-"}</p>
      </section>

      <section className="panel stack-md">
        <p className="panel-label">สรุปตามรายการที่เลือกได้</p>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>{FILTER_MODE_LABELS[filterMode]}</th>
                <th>ทั้งหมด</th>
                <th>พบผู้ป่วย</th>
                <th>ต้องตรวจทาน</th>
                <th>มีประวัติ</th>
                <th>ข้อมูลไม่พอ</th>
              </tr>
            </thead>
            <tbody>
              {visibleSummary.map((row) => (
                <tr key={row.disease_key}>
                  <td>{row.disease_group_label ?? row.disease_key}</td>
                  <td>{row.total_rows}</td>
                  <td>{row.matched_rows}</td>
                  <td>{row.needs_review_rows}</td>
                  <td>{row.disease_positive_rows}</td>
                  <td>{row.disease_unknown_rows}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel stack-md">
        <p className="panel-label">ผลลัพธ์รายบุคคล</p>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>ชื่อ-สกุล</th>
                <th>PID</th>
                <th>HN</th>
                <th>ผลการจับคู่</th>
                <th>รายการที่พบ</th>
                <th>มีประวัติ</th>
                <th>วันที่ล่าสุด</th>
                <th>จำนวนครั้ง</th>
                <th>วันตั้งแต่ครั้งล่าสุด</th>
                <th>ประวัติผู้ป่วย</th>
              </tr>
            </thead>
            <tbody>
              {filteredResults.map((row) => (
                <tr key={row.id}>
                  <td>
                    {row.full_name ?? "-"}
                    {row.flags.length > 0 ? <div className="muted small-text">{row.flags.map((flag) => flag.message).join(", ")}</div> : null}
                  </td>
                  <td>{row.pid ?? "-"}</td>
                  <td>{row.hn ?? "-"}</td>
                  <td>{translateMatchStatus(row.match_status)}</td>
                  <td>
                    {row.matched_service_items.length > 0
                      ? row.matched_service_items.join(", ")
                      : row.matched_disease_labels.join(", ") || "-"}
                  </td>
                  <td>{translateHistoryValue(row.has_disease_history)}</td>
                  <td>{row.latest_visit_date ?? "-"}</td>
                  <td>{row.visit_count ?? "-"}</td>
                  <td>{row.days_since_latest_visit ?? "-"}</td>
                  <td>{row.patient_id ? <Link href={`/patients/${row.patient_id}`}>เปิดดู</Link> : "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
