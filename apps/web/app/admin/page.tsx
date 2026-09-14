"use client";

import { useEffect, useState } from "react";
import { ApiError, api } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import { translateError } from "@/lib/errors";
import type { User } from "@/lib/types";

export default function AdminPage() {
  const { user, loading: authLoading } = useAuth();
  const [users, setUsers] = useState<User[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  function load() {
    api
      .adminListUsers()
      .then(setUsers)
      .catch((e) => setError(e instanceof ApiError ? translateError(e.code, e.message) : "목록을 불러오지 못했습니다."));
  }

  useEffect(() => {
    if (authLoading || !user?.is_admin) return;
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authLoading, user]);

  async function handleApprove(target: User) {
    setBusyId(target.id);
    try {
      await api.adminApprove(target.id);
      load();
    } catch (e) {
      setError(e instanceof ApiError ? translateError(e.code, e.message) : "승인에 실패했습니다.");
    } finally {
      setBusyId(null);
    }
  }

  async function handleUnapprove(target: User) {
    setBusyId(target.id);
    try {
      await api.adminUnapprove(target.id);
      load();
    } catch (e) {
      setError(e instanceof ApiError ? translateError(e.code, e.message) : "승인 취소에 실패했습니다.");
    } finally {
      setBusyId(null);
    }
  }

  async function handleDelete(target: User) {
    const ok = window.confirm(`"${target.email}" 계정을 삭제할까요? 되돌릴 수 없습니다.`);
    if (!ok) return;

    setBusyId(target.id);
    try {
      await api.adminDeleteUser(target.id);
      setUsers((prev) => prev?.filter((u) => u.id !== target.id) ?? prev);
    } catch (e) {
      setError(e instanceof ApiError ? translateError(e.code, e.message) : "삭제에 실패했습니다.");
    } finally {
      setBusyId(null);
    }
  }

  if (authLoading) return <p className="text-sm text-white/50">불러오는 중…</p>;

  if (!user) {
    return (
      <div className="space-y-4">
        <h1 className="text-lg font-semibold">관리자</h1>
        <p className="text-sm text-white/50">로그인이 필요합니다.</p>
        <a href="/login" className="inline-block rounded-md bg-accent text-ink font-medium px-4 py-2 text-sm">
          로그인
        </a>
      </div>
    );
  }

  if (!user.is_admin) {
    return (
      <div className="space-y-4">
        <h1 className="text-lg font-semibold">관리자</h1>
        <p className="text-sm text-white/50">관리자만 접근할 수 있습니다.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold">관리자 — 회원 관리</h1>
        <a href="/admin/models" className="text-sm text-accent hover:underline">
          보이스 모델 관리 →
        </a>
      </div>
      {error && <p className="text-sm text-red-400">{error}</p>}
      {users === null && !error && <p className="text-sm text-white/50">불러오는 중…</p>}

      <div className="space-y-2">
        {users?.map((u) => (
          <div
            key={u.id}
            className="flex flex-col sm:flex-row sm:items-center gap-3 rounded-lg border border-white/10 bg-panel p-3"
          >
            <div className="flex-1 min-w-0">
              <p className="font-medium truncate">
                {u.email}
                {u.is_admin && <span className="ml-2 text-xs text-accent whitespace-nowrap">관리자</span>}
              </p>
              <p className="text-xs text-white/50 truncate">
                {u.is_approved ? "승인됨" : "승인 대기"} · 가입 {new Date(u.created_at).toLocaleString("ko-KR")}
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-2 sm:shrink-0">
              {u.is_approved ? (
                <button
                  onClick={() => handleUnapprove(u)}
                  disabled={busyId === u.id}
                  className="rounded-md border border-white/10 hover:border-white/30 px-3 py-1.5 text-xs whitespace-nowrap disabled:opacity-40"
                >
                  {busyId === u.id ? "…" : "승인 취소"}
                </button>
              ) : (
                <button
                  onClick={() => handleApprove(u)}
                  disabled={busyId === u.id}
                  className="rounded-md bg-accent text-ink font-medium px-3 py-1.5 text-xs whitespace-nowrap disabled:opacity-40"
                >
                  {busyId === u.id ? "…" : "승인"}
                </button>
              )}
              <button
                onClick={() => handleDelete(u)}
                disabled={busyId === u.id}
                title="삭제"
                className="rounded-md border border-white/10 hover:border-red-400 hover:text-red-400 px-2 py-1.5 text-xs whitespace-nowrap disabled:opacity-40"
              >
                {busyId === u.id ? "…" : "🗑"}
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
