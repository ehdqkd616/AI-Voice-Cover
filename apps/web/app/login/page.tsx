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

  async function handleSubmit(email: string, password: string) {
    setLoading(true);
    setError(null);
    try {
      await api.login(email, password);
      await refresh();
      router.push("/");
    } catch (e) {
      setError(e instanceof ApiError ? translateError(e.code, e.message) : "로그인에 실패했습니다.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4">
      <h1 className="text-lg font-semibold">로그인</h1>
      <AuthForm mode="login" onSubmit={handleSubmit} loading={loading} error={error} />
      <p className="text-sm text-white/50">
        계정이 없으신가요? <a href="/signup" className="text-accent">회원가입</a>
      </p>
    </div>
  );
}
