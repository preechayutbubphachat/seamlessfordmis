import "./globals.css";

import { ReactNode } from "react";

export const metadata = {
  title: "Seamless for DMIS",
  description: "Hospital operations data sync and cohort review"
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
