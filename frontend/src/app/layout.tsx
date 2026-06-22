import type { Metadata } from "next";
import { Sarabun, IBM_Plex_Sans_Thai } from "next/font/google";

import { Header } from "@/components/layout/Header";
import { Sidebar } from "@/components/layout/Sidebar";
import { APP_NAME_TH } from "@/lib/constants";

import "./globals.css";

const bodyFont = IBM_Plex_Sans_Thai({
  subsets: ["thai", "latin"],
  weight: ["300", "400", "500", "600"],
});

const displayFont = Sarabun({
  subsets: ["thai", "latin"],
  weight: ["400", "600", "700"],
  variable: "--font-display",
});

export const metadata: Metadata = {
  title: APP_NAME_TH,
  description: "ระบบภายในโรงพยาบาลสำหรับซิงก์ฐานข้อมูลการตรวจโรคและค้นย้อนหลังตามกลุ่มเป้าหมาย",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="th">
      <body className={`${bodyFont.className} ${displayFont.variable}`}>
        <div className="app-shell">
          <Sidebar />
          <main className="main-column">
            <Header />
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}
