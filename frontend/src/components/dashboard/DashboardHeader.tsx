"use client";

import { UploadCTAButton } from "@/components/dashboard/UploadCTAButton";

export function DashboardHeader() {
  return (
    <header className="db-header">
      <div className="db-header-title">
        <p className="eyebrow">DASHBOARD</p>
        <h2>จัดการข้อมูลการคัดกรองโรค</h2>
        <p className="db-subtitle">
          จัดการและนำเข้าข้อมูลการคัดกรองจากหลายแหล่ง เพื่อให้ฐานข้อมูลพร้อมใช้งานและปลอดภัย
        </p>
      </div>
      <UploadCTAButton />
    </header>
  );
}
