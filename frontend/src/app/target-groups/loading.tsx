import { PageLoadingSkeleton } from "@/components/common/PageLoadingSkeleton";

export default function TargetGroupsLoading() {
  return (
    <PageLoadingSkeleton
      title="โปรดรอสักครู่..."
      message="กำลังโหลดข้อมูลกลุ่มเป้าหมายและรายการนำเข้าล่าสุด..."
      cards={2}
      rows={6}
    />
  );
}
