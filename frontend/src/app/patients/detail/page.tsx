"use client";

// D4: query-param detail page (/patients/detail?id=...) replaces /patients/[id].
import { Suspense, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";

import { LoadingState } from "@/components/common/LoadingState";
import { RetryErrorState } from "@/components/common/RetryErrorState";
import { PatientHeader } from "@/components/patients/PatientHeader";
import { PatientTimeline } from "@/components/patients/PatientTimeline";
import { getApiErrorMessage, getPatientHistory } from "@/lib/api";
import type { PatientHistory } from "@/types/patient";

function PatientDetailInner() {
  const searchParams = useSearchParams();
  const id = searchParams.get("id");

  const [history, setHistory] = useState<PatientHistory | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    if (!id) {
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      setHistory(await getPatientHistory(id));
      setError(null);
    } catch (err) {
      setHistory(null);
      setError(getApiErrorMessage(err, "โหลดประวัติผู้ป่วยไม่สำเร็จ"));
    }
    setLoading(false);
  }, [id]);

  useEffect(() => {
    void load();
  }, [load]);

  if (!id) {
    return (
      <RetryErrorState
        title="ไม่พบรหัสผู้ป่วย"
        detail="URL ต้องอยู่ในรูปแบบ /patients/detail?id=<patient_id>"
      />
    );
  }

  if (loading) {
    return <LoadingState title="กำลังโหลดประวัติผู้ป่วย" />;
  }

  if (error || !history) {
    return <RetryErrorState title="ไม่สามารถโหลดประวัติผู้ป่วยได้" detail={error ?? "-"} onRetry={() => void load()} />;
  }

  return (
    <div className="stack-layout">
      <PatientHeader patient={history.patient} />
      <PatientTimeline history={history.history} />
    </div>
  );
}

export default function PatientDetailPage() {
  return (
    <Suspense fallback={<LoadingState title="กำลังโหลดประวัติผู้ป่วย" />}>
      <PatientDetailInner />
    </Suspense>
  );
}
