import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "@/lib/auth-context";
import SiteHeader from "./site-header";

export const metadata: Metadata = {
  title: "AI Voice Cover",
  description: "노래 커버를 자동으로 만들어드려요 — 음원 업로드, 보이스 변환, MR 믹스까지 한 번에",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body className="min-h-screen">
        <AuthProvider>
          <SiteHeader />
          <main className="max-w-3xl mx-auto px-6 py-10">{children}</main>
          <footer className="max-w-3xl mx-auto px-6 pb-10 text-xs text-white/30">
            보컬/반주 분리(Demucs)와 보이스 변환(RVC)은 모두 서버에서 처리됩니다.
          </footer>
        </AuthProvider>
      </body>
    </html>
  );
}
