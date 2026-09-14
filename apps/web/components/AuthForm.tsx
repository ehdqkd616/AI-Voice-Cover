"use client";

import { FormEvent, useState } from "react";

interface Props {
  mode: "login" | "signup";
  onSubmit: (email: string, password: string) => void;
  loading?: boolean;
  error?: string | null;
}

export default function AuthForm({ mode, onSubmit, loading, error }: Props) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    onSubmit(email, password);
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3 max-w-sm">
      <input
        type="email"
        required
        placeholder="이메일"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        className="w-full rounded-md bg-panel border border-white/10 px-3 py-2 text-sm outline-none focus:border-accent"
      />
      <input
        type="password"
        required
        minLength={8}
        placeholder="비밀번호 (8자 이상)"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        className="w-full rounded-md bg-panel border border-white/10 px-3 py-2 text-sm outline-none focus:border-accent"
      />
      {error && <p className="text-sm text-red-400">{error}</p>}
      <button
        type="submit"
        disabled={loading}
        className="rounded-md bg-accent text-ink font-medium px-4 py-2 text-sm disabled:opacity-50"
      >
        {loading ? "처리 중…" : mode === "login" ? "로그인" : "회원가입"}
      </button>
    </form>
  );
}
