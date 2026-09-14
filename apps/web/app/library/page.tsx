"use client";

import { useEffect, useState } from "react";
import { ApiError, api, mediaDownloadUrl, mediaStreamUrl } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import { translateError } from "@/lib/errors";
import type { LibraryItem } from "@/lib/types";

const SOURCE_LABEL: Record<string, string> = {
  youtube: "유튜브",
  upload: "파일 업로드",
};

function formatDuration(sec: number | null): string {
  if (sec === null) return "";
  const m = Math.floor(sec / 60);
  const s = Math.round(sec % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export default function LibraryPage() {
  const { user, loading: authLoading } = useAuth();
  const [items, setItems] = useState<LibraryItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  function load() {
    api
      .library()
      .then(setItems)
      .catch((e) => setError(e instanceof ApiError ? translateError(e.code, e.message) : "목록을 불러오지 못했습니다."));
  }

  useEffect(() => {
    if (authLoading || !user) return;
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authLoading, user]);

  async function handleDelete(item: LibraryItem) {
    const ok = window.confirm(`"${item.title ?? "이 커버"}"를 삭제할까요? 원본 음원과 변환 결과가 모두 삭제되며 되돌릴 수 없습니다.`);
    if (!ok) return;

    setBusyId(item.job_id);
    try {
      await api.deleteLibraryItem(item.job_id);
      setItems((prev) => prev?.filter((i) => i.job_id !== item.job_id) ?? prev);
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
        <h1 className="text-lg font-semibold">내 작업</h1>
        <p className="text-sm text-white/50">로그인이 필요합니다.</p>
        <a href="/login" className="inline-block rounded-md bg-accent text-ink font-medium px-4 py-2 text-sm">
          로그인
        </a>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <h1 className="text-lg font-semibold">내 작업</h1>
      {error && <p className="text-sm text-red-400">{error}</p>}
      {items === null && !error && <p className="text-sm text-white/50">불러오는 중…</p>}
      {items?.length === 0 && <p className="text-sm text-white/50">아직 만든 커버가 없습니다.</p>}

      <div className="space-y-3">
        {items?.map((item) => (
          <div key={item.job_id} className="space-y-2 rounded-lg border border-white/10 bg-panel p-3">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
              <div className="min-w-0">
                <p className="font-medium truncate">{item.title ?? "(제목 없음)"}</p>
                <p className="text-xs text-white/50 truncate">
                  {item.voice_model_name && <span>{item.voice_model_name} 모델</span>}
                  {item.duration_sec !== null && <span> · {formatDuration(item.duration_sec)}</span>}
                  {item.source_type && <span> · {SOURCE_LABEL[item.source_type] ?? item.source_type}</span>}
                  <span> · {new Date(item.created_at).toLocaleString("ko-KR")}</span>
                </p>
              </div>
              <button
                onClick={() => handleDelete(item)}
                disabled={busyId === item.job_id}
                title="삭제"
                className="self-start sm:self-auto rounded-md border border-white/10 hover:border-red-400 hover:text-red-400 px-2 py-1.5 text-xs whitespace-nowrap disabled:opacity-40"
              >
                {busyId === item.job_id ? "…" : "🗑"}
              </button>
            </div>
            <div className="flex flex-col sm:flex-row sm:items-center gap-2">
              {/* eslint-disable-next-line jsx-a11y/media-has-caption */}
              <audio controls src={mediaStreamUrl(item.media_id)} className="w-full sm:flex-1" />
              <a
                href={mediaDownloadUrl(item.media_id)}
                className="shrink-0 text-center rounded-md border border-white/10 hover:border-accent hover:text-accent px-3 py-1.5 text-xs whitespace-nowrap"
              >
                다운로드
              </a>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
