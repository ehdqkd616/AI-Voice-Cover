"use client";

import { useState } from "react";
import { ApiError, api } from "@/lib/api-client";
import { translateError } from "@/lib/errors";
import UrlInput from "./UrlInput";
import type { YoutubeInfoResponse } from "@/lib/types";

export type SourceInput =
  | { kind: "media"; media_id: string; title: string | null }
  | { kind: "youtube"; youtube_url: string; title: string };

interface Props {
  onReady: (input: SourceInput) => void;
}

type Tab = "upload" | "youtube";

export default function SourcePicker({ onReady }: Props) {
  const [tab, setTab] = useState<Tab>("upload");
  const [uploading, setUploading] = useState(false);
  const [fetchingInfo, setFetchingInfo] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<{ info: YoutubeInfoResponse; url: string } | null>(null);

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setError(null);
    setUploading(true);
    try {
      const res = await api.upload(file);
      onReady({ kind: "media", media_id: res.media_id, title: res.title });
    } catch (err) {
      setError(err instanceof ApiError ? translateError(err.code, err.message) : "업로드에 실패했습니다.");
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  }

  async function handleYoutubeSubmit(url: string) {
    setError(null);
    setFetchingInfo(true);
    try {
      const info = await api.youtubeInfo(url);
      setPreview({ info, url });
    } catch (err) {
      setError(err instanceof ApiError ? translateError(err.code, err.message) : "정보를 가져오지 못했습니다.");
    } finally {
      setFetchingInfo(false);
    }
  }

  function confirmYoutube() {
    if (!preview) return;
    onReady({ kind: "youtube", youtube_url: preview.url, title: preview.info.title });
  }

  return (
    <div className="space-y-4">
      <div className="flex gap-2 text-sm">
        <button
          onClick={() => {
            setTab("upload");
            setError(null);
          }}
          className={`rounded-md border px-3 py-1.5 ${
            tab === "upload" ? "border-accent text-accent bg-accent/10" : "border-white/10 text-white/70 hover:border-white/30"
          }`}
        >
          파일 업로드
        </button>
        <button
          onClick={() => {
            setTab("youtube");
            setError(null);
          }}
          className={`rounded-md border px-3 py-1.5 ${
            tab === "youtube" ? "border-accent text-accent bg-accent/10" : "border-white/10 text-white/70 hover:border-white/30"
          }`}
        >
          유튜브 URL
        </button>
      </div>

      {tab === "upload" && (
        <div className="space-y-2">
          <input
            type="file"
            accept="audio/*"
            disabled={uploading}
            onChange={handleFileChange}
            className="block w-full text-sm text-white/70 file:mr-3 file:rounded-md file:border-0 file:bg-accent file:text-ink file:font-medium file:px-4 file:py-2 file:text-sm disabled:opacity-50"
          />
          {uploading && <p className="text-sm text-white/50">업로드 중…</p>}
        </div>
      )}

      {tab === "youtube" && (
        <div className="space-y-3">
          <UrlInput onSubmit={handleYoutubeSubmit} loading={fetchingInfo} />
          {preview && (
            <div className="flex gap-3 rounded-lg border border-white/10 bg-panel p-3">
              {preview.info.thumbnail && (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={preview.info.thumbnail} alt="" className="w-24 h-auto rounded-md shrink-0" />
              )}
              <div className="min-w-0 flex-1 space-y-1">
                <p className="text-sm font-medium truncate">{preview.info.title}</p>
                <p className="text-xs text-white/50 truncate">
                  {preview.info.channel} · {Math.floor(preview.info.duration_sec / 60)}분{" "}
                  {preview.info.duration_sec % 60}초
                </p>
                <button
                  onClick={confirmYoutube}
                  className="rounded-md bg-accent text-ink font-medium px-3 py-1.5 text-xs"
                >
                  이 영상으로 계속하기
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {error && <p className="text-sm text-red-400">{error}</p>}
    </div>
  );
}
