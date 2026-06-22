"use client";

import { useState, useTransition } from "react";

import { checkSourceUpdate, getApiErrorMessage } from "@/lib/api";
import type { SourceCheck } from "@/types/system";

function CopyHashButton({ hash }: { hash: string }) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(hash);
      } else {
        const textArea = document.createElement("textarea");
        textArea.value = hash;
        textArea.setAttribute("readonly", "");
        textArea.style.position = "fixed";
        textArea.style.opacity = "0";
        document.body.appendChild(textArea);
        textArea.select();
        document.execCommand("copy");
        textArea.remove();
      }
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    }
  }

  return (
    <button type="button" className="db-copy-btn icon-only-btn" onClick={handleCopy} title={copied ? "คัดลอกแล้ว" : "คัดลอก hash"}>
      {copied ? "คัดลอกแล้ว" : (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
          <rect x="9" y="9" width="13" height="13" rx="2" />
          <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
        </svg>
      )}
    </button>
  );
}

export function SourceIntegrityCard({ sourceCheck }: { sourceCheck: SourceCheck }) {
  const [current, setCurrent] = useState(sourceCheck);
  const [message, setMessage] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();
  const hash = current.source_set_hash ?? null;
  const detectedFiles = current.files ?? [];
  const verifiedCount = detectedFiles.filter((f) => !f.error_message).length;

  function handleCheckLatest() {
    startTransition(async () => {
      setMessage("กำลังตรวจสอบไฟล์ล่าสุด...");
      try {
        const next = await checkSourceUpdate();
        setCurrent(next);
        setMessage(next.changed ? "พบการเปลี่ยนแปลงของชุดไฟล์ต้นทาง" : "ไฟล์ล่าสุดยังตรงกับฐานข้อมูล");
      } catch (error) {
        setMessage(getApiErrorMessage(error, "ตรวจสอบไฟล์ล่าสุดไม่สำเร็จ"));
      }
    });
  }

  return (
    <section className="panel db-middle-card">
      <div className="panel-head">
        <div>
          <p className="eyebrow">SOURCE INTEGRITY</p>
          <h3>ความสมบูรณ์ของแหล่งข้อมูล</h3>
        </div>
        <span className={`status-chip ${current.changed ? "warning" : "ready"}`}>
          {current.changed ? "ต้องซิงก์ใหม่" : "สมบูรณ์"}
        </span>
      </div>

      {hash ? (
        <div className="db-hash-row">
          <span className="db-hash-label">Source-set hash (ปัจจุบัน)</span>
          <div className="db-hash-value-row">
            <code className="db-hash-code">{hash}</code>
            <CopyHashButton hash={hash} />
          </div>
        </div>
      ) : (
        <div className="empty-state-box compact-empty">
          <p>ยังไม่มี source-set hash สำหรับชุดไฟล์ปัจจุบัน</p>
        </div>
      )}

      <dl className="db-integrity-list">
        <div>
          <dt>จำนวนไฟล์ต้นทาง</dt>
          <dd>{current.source_file_count ?? "-"} ไฟล์</dd>
        </div>
        <div>
          <dt>สถานะการเปลี่ยนแปลง</dt>
          <dd>{current.changed ? "ชุดไฟล์ล่าสุดยังไม่ตรงกับฐานข้อมูล" : "ชุดไฟล์ล่าสุดตรงกับฐานข้อมูล"}</dd>
        </div>
        <div>
          <dt>ไฟล์ต้นทางที่ตรวจพบ</dt>
          <dd>{detectedFiles.length ? `${verifiedCount} / ${detectedFiles.length} ไฟล์` : "-"}</dd>
        </div>
        <div>
          <dt>ผลการตรวจสอบความสมบูรณ์</dt>
          <dd className={current.changed ? "text-warning" : "text-accent"}>
            {current.changed ? "ต้องตรวจสอบและซิงก์" : "ผ่านการตรวจสอบ"}
          </dd>
        </div>
      </dl>

      <button
        type="button"
        className="secondary-button compact-button db-full-button"
        disabled={isPending}
        onClick={handleCheckLatest}
      >
        {isPending ? "กำลังตรวจสอบ..." : "ตรวจสอบไฟล์ล่าสุด"}
      </button>
      {message && <p className="db-card-feedback">{message}</p>}
    </section>
  );
}
