"use client";

import { FormEvent, useState } from "react";
import { inputClass } from "@/components/AuthForm";
import { ApiError, api } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import { translateError } from "@/lib/errors";

export default function AccountPage() {
  const { user, loading } = useAuth();
  const [form, setForm] = useState({ current: "", next: "", next2: "" });
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  if (loading) return <p className="text-sm text-white/50">불러오는 중…</p>;
  if (!user) {
    return (
      <div className="space-y-4">
        <h1 className="text-lg font-semibold">내 정보</h1>
        <a href="/login" className="inline-block rounded-md bg-accent text-ink font-medium px-4 py-2 text-sm">로그인</a>
      </div>
    );
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (form.next !== form.next2) return setMsg({ ok: false, text: "새 비밀번호 확인이 일치하지 않습니다." });
    try {
      await api.changePassword(form.current, form.next);
      setForm({ current: "", next: "", next2: "" });
      setMsg({ ok: true, text: "비밀번호를 바꿨습니다. 다른 기기에서는 로그아웃됩니다." });
    } catch (err) {
      setMsg({ ok: false, text: err instanceof ApiError ? translateError(err.code, err.message) : "비밀번호를 바꾸지 못했습니다." });
    }
  }

  return (
    <div className="space-y-6 max-w-sm">
      <h1 className="text-lg font-semibold">내 정보</h1>
      <dl className="grid grid-cols-[5rem_1fr] gap-y-1 text-sm">
        <dt className="text-white/50">아이디</dt><dd className="break-all">{user.username}</dd>
        <dt className="text-white/50">이름</dt><dd>{user.name || "-"}</dd>
        <dt className="text-white/50">가입일</dt><dd>{new Date(user.created_at).toLocaleDateString("ko-KR")}</dd>
      </dl>
      {user.password_managed ? (
        <p className="text-sm text-white/50">관리자 비밀번호는 서버 .env의 ADMIN_PASSWORD로 관리합니다.</p>
      ) : (
        <form onSubmit={submit} className="space-y-3">
          <h2 className="text-sm font-semibold">비밀번호 변경</h2>
          <input type="password" required autoComplete="current-password" placeholder="현재 비밀번호"
            value={form.current} onChange={(e) => setForm({ ...form, current: e.target.value })} className={inputClass} />
          <input type="password" required minLength={8} maxLength={72} autoComplete="new-password" placeholder="새 비밀번호 (8자 이상)"
            value={form.next} onChange={(e) => setForm({ ...form, next: e.target.value })} className={inputClass} />
          <input type="password" required autoComplete="new-password" placeholder="새 비밀번호 확인"
            value={form.next2} onChange={(e) => setForm({ ...form, next2: e.target.value })} className={inputClass} />
          {msg && <p className={`text-sm ${msg.ok ? "text-emerald-300" : "text-red-400"}`}>{msg.text}</p>}
          <button type="submit" className="rounded-md bg-accent text-ink font-medium px-4 py-2 text-sm">변경</button>
        </form>
      )}
    </div>
  );
}
