"use client";

import { FormEvent, useState } from "react";

// 로그인 폼. 가입은 항목이 많아 app/signup/page.tsx에서 따로 그린다.
interface Props {
  onSubmit: (username: string, password: string) => void;
  loading?: boolean;
  error?: string | null;
}

export const inputClass =
  "w-full rounded-md bg-panel border border-white/10 px-3 py-2 text-sm outline-none focus:border-accent";

export default function AuthForm({ onSubmit, loading, error }: Props) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    onSubmit(username.trim(), password);
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3 max-w-sm">
      {/* 예전 이메일 아이디로도 로그인해야 해서 형식은 제한하지 않는다 */}
      <input type="text" required autoComplete="username" autoCapitalize="none" placeholder="아이디"
        value={username} onChange={(e) => setUsername(e.target.value)} className={inputClass} />
      <input type="password" required autoComplete="current-password" placeholder="비밀번호"
        value={password} onChange={(e) => setPassword(e.target.value)} className={inputClass} />
      {error && <p className="text-sm text-red-400">{error}</p>}
      <button type="submit" disabled={loading}
        className="rounded-md bg-accent text-ink font-medium px-4 py-2 text-sm disabled:opacity-50">
        {loading ? "처리 중…" : "로그인"}
      </button>
    </form>
  );
}
