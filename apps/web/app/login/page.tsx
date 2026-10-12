"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import AuthForm from "@/components/AuthForm";
import { ApiError, api } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import { translateError } from "@/lib/errors";

export default function LoginPage() {
  const router = useRouter();
  const { refresh } = useAuth();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(username: string, password: string) {
    setLoading(true);
    setError(null);
    try {
      await api.login(username, password);
      await refresh();
      router.push("/");
    } catch (e) {
      if (e instanceof ApiError) {
        const reason = typeof e.detail?.reason === "string" ? ` (사유: ${e.detail.reason})` : "";
        // 잠금·검증 오류처럼 서버 메시지가 더 구체적인 경우는 그대로 보여 준다
        setError((e.code === "LOGIN_LOCKED" ? e.message : translateError(e.code, e.message)) + reason);
      } else {
        setError("로그인에 실패했습니다.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4">
      <h1 className="text-lg font-semibold">로그인</h1>
      <AuthForm onSubmit={handleSubmit} loading={loading} error={error} />
      <p className="text-sm text-white/50">
        계정이 없으신가요? <a href="/signup" className="text-accent">회원가입</a>
      </p>
    </div>
  );
}
