import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Spreadsheet Deep Analyzer",
  description: "Analisis formula, dependency, dan struktur Google Sheets",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="id">
      <body>{children}</body>
    </html>
  );
}
