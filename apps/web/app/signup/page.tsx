"use client";

import { FormEvent, useState } from "react";
import { inputClass } from "@/components/AuthForm";
import { ApiError, api } from "@/lib/api-client";
import { translateError } from "@/lib/errors";

const EMPTY = { username: "", name: "", password: "", confirm: "", signup_note: "", agree_terms: false, agree_privacy: false };

export default function SignupPage() {
  const [form, setForm] = useState(EMPTY);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (form.password !== form.confirm) return setError("비밀번호가 일치하지 않습니다.");
    if (!form.agree_terms || !form.agree_privacy) return setError("이용약관과 개인정보 처리방침에 동의해 주세요.");
    setLoading(true);
    setError(null);
    try {
      const { message } = await api.signup({
        username: form.username.trim(),
        name: form.name.trim(),
        password: form.password,
        signup_note: form.signup_note.trim() || undefined,
        agree_terms: true,
        agree_privacy: true,
      });
      setDone(message);
    } catch (e) {
      setError(e instanceof ApiError ? translateError(e.code, e.message) : "회원가입에 실패했습니다.");
    } finally {
      setLoading(false);
    }
  }

  if (done) {
    return (
      <div className="space-y-4">
        <h1 className="text-lg font-semibold">가입 신청 완료</h1>
        <p className="text-sm text-white/50">{done}</p>
        <a href="/login" className="inline-block rounded-md bg-accent text-ink font-medium px-4 py-2 text-sm">로그인 화면으로</a>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <h1 className="text-lg font-semibold">회원가입</h1>
      <p className="text-sm text-white/50">가입 후 관리자 승인이 끝나면 이용할 수 있어요.</p>
      <form onSubmit={handleSubmit} className="space-y-3 max-w-sm">
        <input type="text" required autoComplete="username" autoCapitalize="none" maxLength={32}
          pattern="[A-Za-z0-9_\-]{3,32}" title="영문, 숫자, _, - 조합 3~32자" placeholder="아이디 (영문·숫자·_·- 3~32자)"
          value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} className={inputClass} />
        <input type="text" required autoComplete="name" maxLength={50} placeholder="이름"
          value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className={inputClass} />
        <input type="password" required minLength={8} maxLength={72} autoComplete="new-password" placeholder="비밀번호 (8자 이상)"
          value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} className={inputClass} />
        <input type="password" required minLength={8} autoComplete="new-password" placeholder="비밀번호 확인"
          value={form.confirm} onChange={(e) => setForm({ ...form, confirm: e.target.value })} className={inputClass} />
        <textarea rows={2} maxLength={1000} placeholder="가입 메모 (선택) — 사용 목적 등을 남기면 승인이 빨라요"
          value={form.signup_note} onChange={(e) => setForm({ ...form, signup_note: e.target.value })} className={inputClass} />
        <details className="text-xs text-white/50 rounded-md bg-panel px-3 py-2">
          <summary className="cursor-pointer text-white/70">이용약관 · 개인정보 처리방침 보기</summary>
          <p className="mt-2"><b>이용약관</b> — 승인된 회원에게 AI 커버·보이스 학습 기능을 제공합니다. 결과물은 AI 생성물이며, 권리가 없는 음원·목소리를 쓰거나 타인을 사칭하는 용도로 사용할 수 없고, 남용 시 이용이 정지될 수 있습니다.</p>
          <p className="mt-2"><b>개인정보 처리방침</b> — 수집 항목: 아이디, 이름, 가입 메모, 접속 기록, 업로드한 음원과 결과물. 이용 목적: 회원 관리와 서비스 제공. 탈퇴를 원하면 관리자에게 요청하세요.</p>
        </details>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={form.agree_terms} onChange={(e) => setForm({ ...form, agree_terms: e.target.checked })} />
          이용약관에 동의합니다 (필수)
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={form.agree_privacy} onChange={(e) => setForm({ ...form, agree_privacy: e.target.checked })} />
          개인정보 수집·이용에 동의합니다 (필수)
        </label>
        {error && <p className="text-sm text-red-400">{error}</p>}
        <button type="submit" disabled={loading || !form.agree_terms || !form.agree_privacy}
          className="rounded-md bg-accent text-ink font-medium px-4 py-2 text-sm disabled:opacity-50">
          {loading ? "처리 중…" : "가입 신청"}
        </button>
      </form>
      <p className="text-sm text-white/50">
        이미 계정이 있으신가요? <a href="/login" className="text-accent">로그인</a>
      </p>
    </div>
  );
}
