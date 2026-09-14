"use client";

import { useState } from "react";
import AuthForm from "@/components/AuthForm";
import { ApiError, api } from "@/lib/api-client";
import { translateError } from "@/lib/errors";

export default function SignupPage() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  async function handleSubmit(email: string, password: string) {
    setLoading(true);
    setError(null);
    try {
      await api.signup(email, password);
      setDone(true);
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
        <p className="text-sm text-white/50">
          관리자 승인 후 로그인하실 수 있어요. 승인되면 알려드릴게요.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <h1 className="text-lg font-semibold">회원가입</h1>
      <AuthForm mode="signup" onSubmit={handleSubmit} loading={loading} error={error} />
      <p className="text-sm text-white/50">
        이미 계정이 있으신가요? <a href="/login" className="text-accent">로그인</a>
      </p>
    </div>
  );
}
