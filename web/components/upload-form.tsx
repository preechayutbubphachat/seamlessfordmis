"use client";

import { FormEvent, useState, useTransition } from "react";
import Link from "next/link";

import { confirmTargetGroup, runMatching, uploadTargetGroup } from "@/lib/api";
import { MatchRunResponse, TargetGroupUploadResponse } from "@/types";

function translateStatus(status: string) {
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

export function UploadForm() {
  const [result, setResult] = useState<TargetGroupUploadResponse | null>(null);
  const [jobStatus, setJobStatus] = useState<string | null>(null);
  const [matchRun, setMatchRun] = useState<MatchRunResponse | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  function submitForm(formData: FormData) {
    setError(null);
    setActionMessage(null);
    setMatchRun(null);
    startTransition(async () => {
      try {
        const response = await uploadTargetGroup(formData);
        if (!response) {
          setError("อัปโหลดไม่สำเร็จ กรุณาตรวจสอบว่า API ทำงานอยู่และไฟล์เป็น Excel ที่รองรับ");
          return;
        }
        setResult(response);
        setJobStatus(response.status);
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "อัปโหลดไม่สำเร็จ กรุณาตรวจสอบว่า API ทำงานอยู่และไฟล์เป็น Excel ที่รองรับ");
      }
    });
  }

  function handleConfirm() {
    if (!result) {
      return;
    }
    setError(null);
    setActionMessage(null);
    startTransition(async () => {
      try {
        const response = await confirmTargetGroup(result.job_id);
        setJobStatus(response.status);
        setActionMessage(`ยืนยันการนำเข้าแล้ว มีข้อมูลที่พร้อมจับคู่ ${response.valid_rows} แถว`);
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "ไม่สามารถยืนยันการนำเข้าได้");
      }
    });
  }

  function handleMatch() {
    if (!result) {
      return;
    }
    setError(null);
    setActionMessage(null);
    startTransition(async () => {
      try {
        const response = await runMatching(result.job_id);
        setJobStatus(response.status);
        setMatchRun(response);
        setActionMessage(`จับคู่เสร็จแล้ว พบ ${response.matched_rows} รายการ, ต้องตรวจทาน ${response.review_rows} รายการ, ไม่พบ ${response.unmatched_rows} รายการ`);
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "ไม่สามารถเริ่มจับคู่ได้");
      }
    });
  }

  return (
    <div className="stack-lg">
      <form
        className="panel stack-md"
        onSubmit={(event: FormEvent<HTMLFormElement>) => {
          event.preventDefault();
          submitForm(new FormData(event.currentTarget));
        }}
      >
        <div>
          <p className="panel-label">อัปโหลดกลุ่มเป้าหมาย</p>
          <h2>นำเข้าไฟล์เพื่อดูตัวอย่างก่อนจับคู่</h2>
          <p className="muted">MVP รอบนี้รองรับ Excel เท่านั้น ส่วน PDF ถูกเลื่อนไว้ก่อนเพื่อหลีกเลี่ยงการเดาค่าจากเอกสาร</p>
        </div>

        <label className="field">
          <span>ชื่อกลุ่ม</span>
          <input name="group_name" type="text" placeholder="กลุ่มเสี่ยงเบาหวาน เมษายน 2569" required />
        </label>

        <label className="field">
          <span>ไฟล์ Excel</span>
          <input name="file" type="file" accept=".xlsx,.xls" required />
        </label>

        <button className="button" type="submit" disabled={isPending}>
          {isPending ? "กำลังอัปโหลด..." : "อัปโหลดและดูตัวอย่าง"}
        </button>
      </form>

      {error ? <section className="panel tone-warning"><p>{error}</p></section> : null}

      {result ? (
        <section className="panel stack-md">
          <div className="stats-grid">
            <div>
              <p className="panel-label">งาน</p>
              <strong>#{result.job_id}</strong>
            </div>
            <div>
              <p className="panel-label">สถานะ</p>
              <strong>{translateStatus(jobStatus ?? result.status)}</strong>
            </div>
            <div>
              <p className="panel-label">แถวที่ใช้ได้</p>
              <strong>{result.valid_rows}</strong>
            </div>
            <div>
              <p className="panel-label">แถวที่มีปัญหา</p>
              <strong>{result.invalid_rows}</strong>
            </div>
          </div>

          <div className="action-row">
            <button className="button" type="button" disabled={isPending || (jobStatus ?? result.status) !== "uploaded"} onClick={handleConfirm}>
              {isPending && (jobStatus ?? result.status) === "uploaded" ? "กำลังยืนยัน..." : "ยืนยันการนำเข้า"}
            </button>
            <button
              className="button secondary"
              type="button"
              disabled={isPending || ((jobStatus ?? result.status) !== "confirmed" && (jobStatus ?? result.status) !== "matched")}
              onClick={handleMatch}
            >
              {isPending && (jobStatus ?? result.status) !== "uploaded" ? "กำลังจับคู่..." : "เริ่มจับคู่"}
            </button>
            <Link className="button secondary link-button" href={`/groups/${result.job_id}`}>
              เปิดหน้าผลลัพธ์
            </Link>
          </div>

          {actionMessage ? <p className="muted">{actionMessage}</p> : null}
          {matchRun ? (
            <div className="stats-grid">
              <div>
                <p className="panel-label">พบผู้ป่วย</p>
                <strong>{matchRun.matched_rows}</strong>
              </div>
              <div>
                <p className="panel-label">ต้องตรวจทาน</p>
                <strong>{matchRun.review_rows}</strong>
              </div>
              <div>
                <p className="panel-label">ไม่พบ</p>
                <strong>{matchRun.unmatched_rows}</strong>
              </div>
            </div>
          ) : null}

          <div>
            <p className="panel-label">ปัญหาที่พบจากการตรวจสอบ</p>
            {result.validation_issues.length === 0 ? (
              <p className="muted">ไม่พบปัญหาระดับแถวในตัวอย่างที่อัปโหลด</p>
            ) : (
              <ul className="simple-list">
                {result.validation_issues.slice(0, 10).map((issue) => (
                  <li key={`${issue.row_number}-${issue.field}`}>
                    แถว {issue.row_number}: {issue.field} - {issue.message}
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div>
            <p className="panel-label">ตัวอย่างข้อมูล</p>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    {Object.keys(result.preview_rows[0] ?? {}).map((key) => (
                      <th key={key}>{key}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {result.preview_rows.map((row, index) => (
                    <tr key={index}>
                      {Object.entries(row).map(([key, value]) => (
                        <td key={key}>{String(value ?? "")}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>
      ) : null}
    </div>
  );
}
