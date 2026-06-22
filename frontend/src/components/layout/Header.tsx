"use client";

import { usePathname } from "next/navigation";

function getPageTitle(pathname: string): string {
  if (pathname.startsWith("/target-groups/")) return "ผลลัพธ์กลุ่มเป้าหมาย";
  if (pathname.startsWith("/target-groups")) return "กลุ่มเป้าหมาย";
  return "ฐานข้อมูลการตรวจโรคและกลุ่มเป้าหมาย";
}

export function Header() {
  const pathname = usePathname();
  const title = getPageTitle(pathname);

  return (
    <header className="page-header">
      <div>
        <p className="eyebrow">Hospital-safe workflow</p>
        <h2>{title}</h2>
      </div>
      <p className="header-note">Excel-first, รองรับ PDF แบบ staged, trace ได้ และไม่เดาข้อมูล</p>
    </header>
  );
}
