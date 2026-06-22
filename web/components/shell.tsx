import Link from "next/link";
import { PropsWithChildren } from "react";

export function Shell({ children }: PropsWithChildren) {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div>
          <p className="eyebrow">ระบบปฏิบัติการโรงพยาบาล</p>
          <h1>Seamless for DMIS</h1>
          <p className="sidebar-copy">
            สำหรับซิงก์ข้อมูล Excel, ตรวจทานกลุ่มเป้าหมาย, และค้นประวัติการตรวจหรือรักษาจากรายการที่ขอเบิก
          </p>
        </div>
        <nav className="nav">
          <Link href="/dashboard">ภาพรวมระบบ</Link>
          <Link href="/target-groups/new">อัปโหลดกลุ่มเป้าหมาย</Link>
          <Link href="/groups/4">ผลลัพธ์กลุ่มล่าสุด</Link>
          <Link href="/patients/16048">ตัวอย่างประวัติผู้ป่วย</Link>
        </nav>
      </aside>
      <main className="content">{children}</main>
    </div>
  );
}
