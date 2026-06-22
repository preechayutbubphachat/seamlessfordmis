"use client";

// D4.7: robust bootstrap-from-URL for the target group result page.
// Every load path (launcher first open, client nav from list, F5 refresh,
// relaunch) fetches from groupId in the URL — no in-memory navigation state.
// Each API call has explicit status (loading/success/error) with retry;
// empty is shown ONLY after a successful response with no data.
import { Suspense, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";

import { LoadingState } from "@/components/common/LoadingState";
import { RetryErrorState } from "@/components/common/RetryErrorState";
import { StageProgress } from "@/components/common/StageProgress";
import { useElapsedSeconds } from "@/components/common/useElapsedSeconds";
import { TargetGroupResultsWorkspace } from "@/components/target-groups/TargetGroupResultsWorkspace";
import { getApiErrorMessage, getDiseaseOptions, getTargetGroup } from "@/lib/api";
import type { DiseaseOption, TargetGroupDetail } from "@/types/target-group";

type FetchStatus = "loading" | "success" | "error";

function debugLog(event: string, detail: Record<string, unknown>) {
  // Desktop/dev diagnostics — never log CID, names, or query payloads.
  console.info(`[tg-detail] ${event}`, detail);
}

function TargetGroupDetailInner() {
  const searchParams = useSearchParams();
  const id = searchParams.get("id");

  const [group, setGroup] = useState<TargetGroupDetail | null>(null);
  const [groupStatus, setGroupStatus] = useState<FetchStatus>("loading");
  const [groupError, setGroupError] = useState<string | null>(null);

  const [diseaseOptions, setDiseaseOptions] = useState<DiseaseOption[] | null>(null);
  const [optionsStatus, setOptionsStatus] = useState<FetchStatus>("loading");
  const [optionsError, setOptionsError] = useState<string | null>(null);

  const loadGroup = useCallback(async (groupId: string, isCancelled?: () => boolean) => {
    setGroupStatus("loading");
    setGroupError(null);
    debugLog("group.fetch.start", { groupId, endpoint: "/api/target-groups/{id}" });
    try {
      const response = await getTargetGroup(groupId);
      if (isCancelled?.()) return;
      setGroup(response);
      setGroupStatus("success");
      debugLog("group.fetch.success", { groupId });
    } catch (error) {
      if (isCancelled?.()) return;
      const message = getApiErrorMessage(error, "โหลดข้อมูลกลุ่มเป้าหมายไม่สำเร็จ");
      setGroup(null);
      setGroupStatus("error");
      setGroupError(message);
      debugLog("group.fetch.error", { groupId, message });
    }
  }, []);

  const loadOptions = useCallback(async (groupId: string, isCancelled?: () => boolean) => {
    setOptionsStatus("loading");
    setOptionsError(null);
    debugLog("options.fetch.start", { groupId, endpoint: "/api/target-groups/disease-options" });
    try {
      const response = await getDiseaseOptions();
      if (isCancelled?.()) return;
      setDiseaseOptions(response);
      setOptionsStatus("success");
      debugLog("options.fetch.success", { groupId, optionCount: response.length });
    } catch (error) {
      if (isCancelled?.()) return;
      const message = getApiErrorMessage(error, "โหลดตัวเลือกโรคไม่สำเร็จ");
      setDiseaseOptions(null);
      setOptionsStatus("error");
      setOptionsError(message);
      debugLog("options.fetch.error", { groupId, message });
    }
  }, []);

  // Reset + refetch whenever the URL id changes. The cancelled flag prevents
  // a stale response from a previous group overwriting the current one.
  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    const isCancelled = () => cancelled;
    setGroup(null);
    setDiseaseOptions(null);
    void loadGroup(id, isCancelled);
    void loadOptions(id, isCancelled);
    return () => {
      cancelled = true;
    };
  }, [id, loadGroup, loadOptions]);

  const isBootstrapping = groupStatus === "loading" || optionsStatus === "loading";
  const elapsed = useElapsedSeconds(isBootstrapping, id);

  if (!id) {
    return (
      <RetryErrorState
        title="ไม่พบรหัสกลุ่มเป้าหมาย"
        detail="URL ต้องอยู่ในรูปแบบ /target-groups/detail?id=<group_id> — กลับไปเลือกกลุ่มจากหน้ารายการกลุ่มเป้าหมาย"
      />
    );
  }

  if (isBootstrapping) {
    // 5-stage pipeline. Stage advances as the parallel fetches resolve; this is
    // stage-based progress, not a real record count.
    const stageIndex = groupStatus === "loading" ? 0 : optionsStatus === "loading" ? 2 : 4;
    return (
      <StageProgress
        title="กำลังโหลดรายละเอียดกลุ่มเป้าหมาย"
        stages={[
          "โหลดข้อมูลกลุ่มเป้าหมาย",
          "ตรวจสอบไฟล์และ validation summary",
          "โหลดรายการโรค/บริการจากฐานข้อมูลการตรวจโรค",
          "โหลด result summary / รายการผลลัพธ์",
          "พร้อมสร้างหรือดูผลลัพธ์",
        ]}
        currentIndex={stageIndex}
        status="loading"
        elapsedSeconds={elapsed}
        onRetry={() => {
          void loadGroup(id);
          void loadOptions(id);
        }}
      />
    );
  }

  if (groupStatus === "error" || !group) {
    return (
      <RetryErrorState
        title="ไม่สามารถโหลดรายละเอียดกลุ่มเป้าหมายได้"
        detail={groupError ?? "-"}
        onRetry={() => void loadGroup(id)}
      />
    );
  }

  return (
    <div className="stack-layout">
      {optionsStatus === "error" ? (
        <RetryErrorState
          title="ไม่สามารถโหลดรายการโรคหรือบริการได้"
          detail={optionsError ?? "-"}
          onRetry={() => void loadOptions(id)}
        />
      ) : null}
      {optionsStatus === "success" && (diseaseOptions?.length ?? 0) === 0 ? (
        <section className="panel error-panel">
          <p className="eyebrow">Disease options</p>
          <h3>ยังไม่พบรายการโรค/บริการในระบบ</h3>
          <p className="summary-copy">
            รายการโรค/บริการมาจากแคตตาล็อกการคัดกรอง (disease mapping) ของระบบ หากเพิ่งติดตั้งใหม่
            ให้เปิดหน้า Dashboard เพื่อโหลด/ซิงก์ฐานข้อมูลการคัดกรอง แล้วกดโหลดรายการใหม่
          </p>
          <div className="button-row section-block">
            <button className="secondary-button" type="button" onClick={() => void loadOptions(id)}>
              โหลดรายการใหม่
            </button>
            <a className="secondary-button compact-button" href="/dashboard">
              ไปหน้า Dashboard
            </a>
          </div>
        </section>
      ) : null}
      <TargetGroupResultsWorkspace
        key={`${id}:${diseaseOptions?.length ?? 0}`}
        groupId={id}
        initialGroup={group}
        diseaseOptions={diseaseOptions ?? []}
        initialResults={null}
      />
    </div>
  );
}

export default function TargetGroupDetailPage() {
  return (
    <Suspense fallback={<LoadingState title="กำลังโหลดรายละเอียดกลุ่มเป้าหมาย" />}>
      <TargetGroupDetailInner />
    </Suspense>
  );
}
