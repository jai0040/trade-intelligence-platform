import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI Trading Intelligence — Multi-Market SaaS Platform",
  description:
    "Signals-Only AI Trading Intelligence platform for Indian (NSE/BSE) and US (NASDAQ/NYSE) equity markets.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body className="min-h-screen font-sans">{children}</body>
    </html>
  );
}
