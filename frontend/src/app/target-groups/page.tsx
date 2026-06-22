"use client";

// D4: client component — fetches at runtime so static export works on desktop.
import { useCallback, useEffect, useState } from "react";

import { LoadingState } from "@/components/common/LoadingState";
import { TargetGroupUploadForm } from "@/components/target-groups/TargetGroupUploadForm";
import { getApiErrorMessage, listTargetGroups } from "@/lib/api";
import type { TargetGroupListItem } from "@/types/target-group";

export default function TargetGroupsPage() {
  const [groups, setGroups] = useState<TargetGroupListItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setGroups(await listTargetGroups());
      setError(null);
    } catch (err) {
      setGroups([]);
      setError(getApiErrorMessage(err, "โหลดรายการกลุ่มเป้าหมายไม่สำเร็จ"));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (groups === null) {
    return <LoadingState title="กำลังโหลดรายการกลุ่มเป้าหมาย" />;
  }

  if (error) {
    return (
      <div className="stack-layout">
        <section className="panel error-panel">
          <p className="eyebrow">Target groups</p>
          <h3>ไม่สามารถโหลดรายการกลุ่มเป้าหมายได้</h3>
          <p className="summary-copy">รายละเอียดข้อผิดพลาด: {error}</p>
        </section>
        <TargetGroupUploadForm recentGroups={[]} />
      </div>
    );
  }

  return <TargetGroupUploadForm recentGroups={groups} />;
}
