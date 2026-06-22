"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const items = [
  {
    href: "/dashboard",
    label: "แดชบอร์ด",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
        <rect x="4" y="7" width="16" height="13" rx="2" />
        <path d="M9 7V5a3 3 0 0 1 6 0v2" />
        <path d="M9 14h6" />
      </svg>
    ),
  },
  {
    href: "/target-groups",
    label: "กลุ่มเป้าหมาย",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
        <path d="M16 21v-2a4 4 0 0 0-8 0v2" />
        <circle cx="12" cy="7" r="4" />
        <path d="M22 21v-2a4 4 0 0 0-3-3.87" />
      </svg>
    ),
  },
];

export function Sidebar() {
  const pathname = usePathname();

  function isActive(href: string) {
    if (href === "/dashboard") return pathname === "/dashboard" || pathname === "/";
    return pathname.startsWith(href);
  }

  return (
    <aside className="sidebar">
      <div className="brand">
        <span className="brand-mark">DR</span>
        <div>
          <p className="brand-eyebrow">Disease Screening</p>
          <h1>ฐานข้อมูลการตรวจโรค</h1>
        </div>
      </div>
      <nav className="nav-list" aria-label="เมนูหลัก">
        {items.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={`nav-item${isActive(item.href) ? " active" : ""}`}
          >
            <span className="nav-icon" aria-hidden="true">{item.icon}</span>
            <span>{item.label}</span>
          </Link>
        ))}
      </nav>
      <div className="sidebar-footer">
        <p className="eyebrow">Build</p>
        <p className="sidebar-build"><span className="build-dot">N</span> v1.3.0 · staging</p>
        <div
          className="local-mode-badge"
          title="ข้อมูลทั้งหมดถูกประมวลผลภายในเครือข่ายของหน่วยงาน — ไม่มีการส่งข้อมูลออกอินเทอร์เน็ต"
        >
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" aria-hidden="true">
            <rect x="3" y="11" width="18" height="11" rx="2" />
            <path d="M7 11V7a5 5 0 0 1 10 0v4" />
          </svg>
          <span>ภายในหน่วยงาน</span>
        </div>
      </div>
    </aside>
  );
}
