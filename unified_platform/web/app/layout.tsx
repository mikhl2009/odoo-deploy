import "./globals.css";

import type { Metadata } from "next";
import { ReactNode } from "react";

import { Sidebar } from "@/components/sidebar";
import { Topbar } from "@/components/topbar";

export const metadata: Metadata = {
  title: "Unified Tobacco ERP",
  description: "Unified all-in-one business management dashboard"
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="app-shell">
          <Sidebar />
          <main className="main-wrap">
            <Topbar />
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}
