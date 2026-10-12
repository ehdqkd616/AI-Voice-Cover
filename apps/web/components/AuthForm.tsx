"use client";

import { FormEvent, useState } from "react";

interface Props {
  mode: "login" | "signup";
  onSubmit: (username: string, password: string) => void;
  loading?: boolean;
  error?: string | null;
}

const inputClass =
  "w-full rounded-md bg-panel border border-white/10 px-3 py-2 text-sm outline-none focus:border-accent";

export default function AuthForm({ mode, onSubmit, loading, error }: Props) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);
  const isSignup = mode === "signup";

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (isSignup && password !== confirm) {
      setLocalError("비밀번호가 일치하지 않습니다.");
      return;
    }
    setLocalError(null);
    onSubmit(username.trim(), password);
  }

  const shownError = localError ?? error;

  return (
    <form onSubmit={handleSubmit} className="space-y-3 max-w-sm">
      <input
        type="text"
        required
        autoComplete="username"
        // 가입은 영문/숫자/_/- 3~32자. 로그인은 예전 이메일 아이디도 받아야 해서 제한하지 않는다.
        pattern={isSignup ? "[A-Za-z0-9_\\-]{3,32}" : undefined}
        title={isSignup ? "영문, 숫자, _, - 조합 3~32자" : undefined}
        placeholder={isSignup ? "아이디 (영문·숫자 3~32자)" : "아이디"}
        value={username}
        onChange={(e) => setUsername(e.target.value)}
        className={inputClass}
      />
      <input
        type="password"
        required
        minLength={isSignup ? 8 : undefined}
        autoComplete={isSignup ? "new-password" : "current-password"}
        placeholder={isSignup ? "비밀번호 (8자 이상)" : "비밀번호"}
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        className={inputClass}
      />
      {isSignup && (
        <input
          type="password"
          required
          minLength={8}
          autoComplete="new-password"
          placeholder="비밀번호 확인"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          className={inputClass}
        />
      )}
      {shownError && <p className="text-sm text-red-400">{shownError}</p>}
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
