"use client";

import { FormEvent, useEffect, useState } from "react";
import { ApiError, api } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import { translateError } from "@/lib/errors";
import type { VoiceModelAdmin } from "@/lib/types";

const CONFIDENCE_STYLE: Record<string, string> = {
  manual: "bg-emerald-400/10 text-emerald-300",
  auto_high: "bg-emerald-400/10 text-emerald-300",
  auto_low: "bg-amber-400/10 text-amber-300",
  unpaired: "bg-red-400/10 text-red-300",
};

export default function AdminModelsPage() {
  const { user, loading: authLoading } = useAuth();
  const [models, setModels] = useState<VoiceModelAdmin[] | null>(null);
  const [unmatched, setUnmatched] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [weightFile, setWeightFile] = useState<File | null>(null);
  const [indexFile, setIndexFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);

  function load() {
    api
      .adminListVoiceModels()
      .then(setModels)
      .catch((e) => setError(e instanceof ApiError ? translateError(e.code, e.message) : "목록을 불러오지 못했습니다."));
    api
      .adminUnmatchedIndices()
      .then(setUnmatched)
      .catch(() => setUnmatched([]));
  }

  useEffect(() => {
    if (authLoading || !user?.is_admin) return;
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authLoading, user]);

  async function handleToggleActive(m: VoiceModelAdmin) {
    setBusyId(m.id);
    try {
      await api.adminUpdateVoiceModel(m.id, { is_active: !m.is_active });
      load();
    } catch (e) {
      setError(e instanceof ApiError ? translateError(e.code, e.message) : "변경에 실패했습니다.");
    } finally {
      setBusyId(null);
    }
  }

  async function handleDelete(m: VoiceModelAdmin) {
    const ok = window.confirm(`"${m.name}" 모델을 삭제할까요? 되돌릴 수 없습니다.`);
    if (!ok) return;
    setBusyId(m.id);
    try {
      await api.adminDeleteVoiceModel(m.id);
      setModels((prev) => prev?.filter((x) => x.id !== m.id) ?? prev);
    } catch (e) {
      setError(e instanceof ApiError ? translateError(e.code, e.message) : "삭제에 실패했습니다.");
    } finally {
      setBusyId(null);
    }
  }

  async function handleRepair(m: VoiceModelAdmin, indexFilename: string) {
    if (!indexFilename) return;
    setBusyId(m.id);
    try {
      await api.adminUpdateVoiceModel(m.id, { index_filename: indexFilename });
      load();
    } catch (e) {
      setError(e instanceof ApiError ? translateError(e.code, e.message) : "재매칭에 실패했습니다.");
    } finally {
      setBusyId(null);
    }
  }

  async function handleUpload(e: FormEvent) {
    e.preventDefault();
    if (!weightFile) return;
    setUploading(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("name", name);
      if (description) form.append("description", description);
      form.append("weight_file", weightFile);
      if (indexFile) form.append("index_file", indexFile);
      await api.adminUploadVoiceModel(form);
      setName("");
      setDescription("");
      setWeightFile(null);
      setIndexFile(null);
      load();
    } catch (e) {
      setError(e instanceof ApiError ? translateError(e.code, e.message) : "업로드에 실패했습니다.");
    } finally {
      setUploading(false);
    }
  }

  if (authLoading) return <p className="text-sm text-white/50">불러오는 중…</p>;

  if (!user) {
    return (
      <div className="space-y-4">
        <h1 className="text-lg font-semibold">보이스 모델 관리</h1>
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
        <h1 className="text-lg font-semibold">보이스 모델 관리</h1>
        <p className="text-sm text-white/50">관리자만 접근할 수 있습니다.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold">관리자 — 보이스 모델 관리</h1>
        <a href="/admin" className="text-sm text-accent hover:underline">
          ← 회원 관리
        </a>
      </div>
      {error && <p className="text-sm text-red-400">{error}</p>}

      <form onSubmit={handleUpload} className="space-y-3 rounded-lg border border-white/10 bg-panel p-4">
        <h2 className="text-sm font-medium">새 보이스 모델 업로드</h2>
        <input
          type="text"
          required
          placeholder="이름"
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="w-full rounded-md bg-ink border border-white/10 px-3 py-2 text-sm outline-none focus:border-accent"
        />
        <input
          type="text"
          placeholder="설명 (선택)"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          className="w-full rounded-md bg-ink border border-white/10 px-3 py-2 text-sm outline-none focus:border-accent"
        />
        <div className="space-y-1">
          <label className="text-xs text-white/50">가중치 파일 (.pth) — 필수</label>
          <input
            type="file"
            accept=".pth"
            required
            onChange={(e) => setWeightFile(e.target.files?.[0] ?? null)}
            className="block w-full text-sm text-white/70 file:mr-3 file:rounded-md file:border-0 file:bg-white/10 file:px-3 file:py-1.5 file:text-xs"
          />
        </div>
        <div className="space-y-1">
          <label className="text-xs text-white/50">인덱스 파일 (.index) — 선택</label>
          <input
            type="file"
            accept=".index"
            onChange={(e) => setIndexFile(e.target.files?.[0] ?? null)}
            className="block w-full text-sm text-white/70 file:mr-3 file:rounded-md file:border-0 file:bg-white/10 file:px-3 file:py-1.5 file:text-xs"
          />
        </div>
        <button
          type="submit"
          disabled={uploading || !weightFile}
          className="rounded-md bg-accent text-ink font-medium px-4 py-2 text-sm disabled:opacity-50"
        >
          {uploading ? "업로드 중…" : "업로드"}
        </button>
      </form>

      <div className="space-y-2">
        {models === null && !error && <p className="text-sm text-white/50">불러오는 중…</p>}
        {models?.map((m) => (
          <div key={m.id} className="space-y-2 rounded-lg border border-white/10 bg-panel p-3">
            <div className="flex flex-col sm:flex-row sm:items-center gap-3">
              <div className="flex-1 min-w-0">
                <p className="font-medium truncate flex items-center gap-2">
                  {m.name}
                  <span
                    className={`rounded-md text-[11px] px-2 py-0.5 whitespace-nowrap ${
                      CONFIDENCE_STYLE[m.pairing_confidence] ?? "bg-white/10 text-white/60"
                    }`}
                  >
                    {m.pairing_confidence}
                  </span>
                  {!m.is_active && (
                    <span className="rounded-md bg-white/10 text-white/50 text-[11px] px-2 py-0.5 whitespace-nowrap">
                      비활성
                    </span>
                  )}
                </p>
                <p className="text-xs text-white/50 truncate">
                  가중치: {m.weight_filename} · 인덱스: {m.index_filename ?? "미매칭"}
                </p>
              </div>

              <div className="flex flex-wrap items-center gap-2 sm:shrink-0">
                <button
                  onClick={() => handleToggleActive(m)}
                  disabled={busyId === m.id}
                  className="rounded-md border border-white/10 hover:border-white/30 px-3 py-1.5 text-xs whitespace-nowrap disabled:opacity-40"
                >
                  {busyId === m.id ? "…" : m.is_active ? "비활성화" : "활성화"}
                </button>
                <button
                  onClick={() => handleDelete(m)}
                  disabled={busyId === m.id}
                  title="삭제"
                  className="rounded-md border border-white/10 hover:border-red-400 hover:text-red-400 px-2 py-1.5 text-xs whitespace-nowrap disabled:opacity-40"
                >
                  {busyId === m.id ? "…" : "🗑"}
                </button>
              </div>
            </div>

            {!m.index_filename && unmatched.length > 0 && (
              <div className="flex items-center gap-2">
                <label className="text-xs text-white/50 whitespace-nowrap">인덱스 재매칭:</label>
                <select
                  defaultValue=""
                  disabled={busyId === m.id}
                  onChange={(e) => handleRepair(m, e.target.value)}
                  className="flex-1 rounded-md bg-ink border border-white/10 px-2 py-1 text-xs outline-none focus:border-accent"
                >
                  <option value="" disabled>
                    파일 선택…
                  </option>
                  {unmatched.map((f) => (
                    <option key={f} value={f}>
                      {f}
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
