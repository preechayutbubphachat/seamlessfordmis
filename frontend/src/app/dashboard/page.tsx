"use client";

// D4: converted from async server component to client component so the
// desktop static export fetches live data from the local backend at runtime.
import { useCallback, useEffect, useState } from "react";

import { DashboardHeader } from "@/components/dashboard/DashboardHeader";
import { DashboardQuickActions } from "@/components/dashboard/DashboardQuickActions";
import { DashboardStatusSummary } from "@/components/dashboard/DashboardStatusSummary";
import { RecentImportsTable } from "@/components/dashboard/RecentImportsTable";
import { ScreeningDataUploadCard } from "@/components/dashboard/ScreeningDataUploadCard";
import { SourceIntegrityCard } from "@/components/dashboard/SourceIntegrityCard";
import { SupportedFileTypesCard } from "@/components/dashboard/SupportedFileTypesCard";
import { LoadingState } from "@/components/common/LoadingState";
import {
  checkSourceUpdate,
  getApiErrorMessage,
  getSystemStatus,
  listScreeningImports,
} from "@/lib/api";
import type { ImportJobListResponse } from "@/types/screening-database";
import type { SourceCheck, SystemStatus } from "@/types/system";

type DashboardData = {
  status: SystemStatus | null;
  sourceCheck: SourceCheck | null;
  importsData: ImportJobListResponse | null;
  statusError: string | null;
  sourceCheckError: string | null;
};

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);

  const load = useCallback(async () => {
    const [statusResult, sourceCheckResult, importsResult] = await Promise.allSettled([
      getSystemStatus(),
      checkSourceUpdate(),
      listScreeningImports(20, 0),
    ]);

    setData({
      status: statusResult.status === "fulfilled" ? statusResult.value : null,
      sourceCheck: sourceCheckResult.status === "fulfilled" ? sourceCheckResult.value : null,
      importsData: importsResult.status === "fulfilled" ? importsResult.value : null,
      statusError:
        statusResult.status === "rejected"
          ? getApiErrorMessage(statusResult.reason, "ไม่สามารถโหลดสถานะระบบได้")
          : null,
      sourceCheckError:
        sourceCheckResult.status === "rejected"
          ? getApiErrorMessage(sourceCheckResult.reason, "ไม่สามารถโหลดสถานะไฟล์ต้นทางได้")
          : null,
    });
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (!data) {
    return (
      <div className="db-page">
        <DashboardHeader />
        <LoadingState title="กำลังโหลดสถานะระบบ" message="กำลังเชื่อมต่อฐานข้อมูลภายในเครื่อง..." />
      </div>
    );
  }

  const { status, sourceCheck, importsData, statusError, sourceCheckError } = data;

  return (
    <div className="db-page">
      <DashboardHeader />

      {status ? (
        <DashboardStatusSummary status={status} />
      ) : (
        <section className="panel error-panel">
          <p className="eyebrow">System status</p>
          <h3>ไม่สามารถโหลดสถานะระบบได้</h3>
          <p className="summary-copy">รายละเอียดข้อผิดพลาด: {statusError ?? "-"}</p>
        </section>
      )}

      <div className="db-middle-grid">
        {sourceCheck ? (
          <SourceIntegrityCard sourceCheck={sourceCheck} />
        ) : (
          <section className="panel error-panel">
            <p className="eyebrow">Source integrity</p>
            <h3>ไม่สามารถโหลดสถานะไฟล์ต้นทางได้</h3>
            <p className="summary-copy">รายละเอียดข้อผิดพลาด: {sourceCheckError ?? "-"}</p>
          </section>
        )}
        <ScreeningDataUploadCard />
        <SupportedFileTypesCard />
      </div>

      <DashboardQuickActions latestImportId={importsData?.imports?.[0]?.import_id ?? null} />

      <RecentImportsTable
        imports={importsData?.imports ?? []}
        total={importsData?.total ?? 0}
      />
    </div>
  );
}
