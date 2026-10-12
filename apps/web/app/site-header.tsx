"use client";

import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth-context";

// The app's two core features get their own prominent tab bar under the top
// bar; account/utility links (내 작업, 관리자, 로그아웃) stay small up top.
const FEATURES = [
  {
    href: "/",
    title: "AI 보이스 커버 만들기",
    short: "커버 만들기",
    desc: "노래를 원하는 목소리로 바꿔 MR과 합쳐요",
    adminOnly: false,
    isActive: (path: string) => path === "/",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} className="h-5 w-5">
        <rect x="9" y="3" width="6" height="11" rx="3" />
        <path d="M5 11a7 7 0 0 0 14 0M12 18v3" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    href: "/train",
    title: "보이스 학습",
    short: "보이스 학습",
    desc: "목소리를 학습시켜 나만의 보이스 모델을 만들어요",
    adminOnly: true,
    isActive: (path: string) => path === "/train" || path.startsWith("/train/"),
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} className="h-5 w-5">
        <path d="M3 12h2M7 8v8M11 5v14M15 9v6M19 7v10M21 12h0" strokeLinecap="round" />
      </svg>
    ),
  },
];

export default function SiteHeader() {
  const { user, loading, logout } = useAuth();
  const pathname = usePathname() ?? "/";
  const features = FEATURES.filter((f) => !f.adminOnly || user?.is_admin);

  return (
    <header className="border-b border-white/10">
      <div className="px-4 sm:px-6 py-3 flex items-center justify-between gap-3">
        <a href="/" className="font-semibold tracking-tight text-lg whitespace-nowrap">
          AI Voice Cover
        </a>
        <nav className="text-xs sm:text-sm text-white/60 flex flex-wrap items-center justify-end gap-x-4 gap-y-1">
          {!loading &&
            (user ? (
              <>
                <a
                  href="/library"
                  className={`whitespace-nowrap hover:text-white ${pathname.startsWith("/library") ? "text-white" : ""}`}
                >
                  내 작업
                </a>
                {user.is_admin && (
                  <a
                    href="/admin"
                    className={`whitespace-nowrap hover:text-white ${pathname.startsWith("/admin") ? "text-white" : ""}`}
                  >
                    관리자
                  </a>
                )}
                <a href="/account" className={`whitespace-nowrap truncate max-w-[10rem] hover:text-white ${pathname.startsWith("/account") ? "text-white" : "text-white/40"}`}>
                  {user.name || user.username}
                </a>
                <button onClick={logout} className="hover:text-white whitespace-nowrap">
                  로그아웃
                </button>
              </>
            ) : (
              <>
                <a href="/login" className="hover:text-white whitespace-nowrap">
                  로그인
                </a>
                <a href="/signup" className="hover:text-white whitespace-nowrap">
                  회원가입
                </a>
              </>
            ))}
        </nav>
      </div>

      {!loading && user && (
        <div className="max-w-3xl mx-auto px-4 sm:px-6 pb-4 pt-1">
          <nav className={`grid gap-2 sm:gap-3 ${features.length > 1 ? "grid-cols-2" : "grid-cols-1"}`}>
            {features.map((f) => {
              const active = f.isActive(pathname);
              return (
                <a
                  key={f.href}
                  href={f.href}
                  aria-current={active ? "page" : undefined}
                  className={`group flex items-center gap-2.5 sm:gap-3 rounded-xl border px-3 py-2.5 sm:px-4 sm:py-3.5 transition-colors ${
                    active
                      ? "border-accent/70 bg-accent/10 shadow-[0_0_0_1px_rgba(110,231,183,0.15)]"
                      : "border-white/10 bg-panel hover:border-white/25 hover:bg-white/[0.04]"
                  }`}
                >
                  <span
                    className={`flex h-8 w-8 sm:h-10 sm:w-10 shrink-0 items-center justify-center rounded-lg ${
                      active ? "bg-accent text-ink" : "bg-white/10 text-white/70 group-hover:text-white"
                    }`}
                  >
                    {f.icon}
                  </span>
                  <span className="min-w-0">
                    <span
                      className={`block text-sm sm:text-base font-semibold leading-tight ${
                        active ? "text-accent" : "text-white/90"
                      }`}
                    >
                      <span className="sm:hidden">{f.short}</span>
                      <span className="hidden sm:inline">{f.title}</span>
                    </span>
                    <span className="mt-0.5 hidden sm:block text-xs text-white/50 truncate">{f.desc}</span>
                  </span>
                </a>
              );
            })}
          </nav>
        </div>
      )}
    </header>
  );
}
