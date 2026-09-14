"use client";

import { useAuth } from "@/lib/auth-context";

export default function SiteHeader() {
  const { user, loading, logout } = useAuth();

  return (
    <header className="border-b border-white/10 px-4 sm:px-6 py-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <a href="/" className="font-semibold tracking-tight text-lg whitespace-nowrap">
        AI Voice Cover
      </a>
      <nav className="text-sm text-white/60 flex flex-wrap items-center gap-x-4 gap-y-2">
        {!loading &&
          (user ? (
            <>
              <a href="/library" className="hover:text-white whitespace-nowrap">
                내 작업
              </a>
              {user.is_admin && (
                <a href="/admin" className="hover:text-white whitespace-nowrap">
                  관리자
                </a>
              )}
              <span className="text-white/40 truncate max-w-[8rem] sm:max-w-[10rem]">{user.email}</span>
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
    </header>
  );
}
