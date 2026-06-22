import { PageLoadingSkeleton } from "@/components/common/PageLoadingSkeleton";

export default function DashboardLoading() {
  return (
    <PageLoadingSkeleton
      title="โปรดรอสักครู่..."
      message="กำลังโหลดสถานะระบบและความพร้อมของฐานข้อมูลการตรวจโรค..."
      cards={3}
      rows={4}
    />
  );
}
