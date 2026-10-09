"use client";

import { useRef, useState } from "react";
import { ApiError, api } from "@/lib/api-client";
import { translateError } from "@/lib/errors";

export interface DatasetFile {
  key: string;
  name: string;
  status: "uploading" | "done" | "error";
  media_id?: string;
  duration_sec?: number | null;
  error?: string;
}

interface Props {
  files: DatasetFile[];
  onChange: (updater: (prev: DatasetFile[]) => DatasetFile[]) => void;
}

const ACCEPT = "audio/*,.mp3,.wav,.m4a,.flac";

export function datasetMinutes(files: DatasetFile[]): number {
  return files.reduce((sum, f) => sum + (f.status === "done" ? f.duration_sec ?? 0 : 0), 0) / 60;
}

export function datasetQuality(minutes: number): { label: string; tone: string; width: number } {
  if (minutes < 1) return { label: "너무 짧아요 — 최소 1분 이상 필요해요", tone: "bg-red-400", width: 8 };
  if (minutes < 5) return { label: "조금 짧아요 — 결과가 불안정할 수 있어요", tone: "bg-amber-400", width: 30 };
  if (minutes < 10) return { label: "괜찮아요 — 10분 이상이면 더 좋아요", tone: "bg-lime-400", width: 60 };
  if (minutes <= 60) return { label: "충분해요 (권장 분량)", tone: "bg-accent", width: 100 };
  return { label: "많아요 — 품질엔 좋지만 학습이 오래 걸려요", tone: "bg-accent", width: 100 };
}

export default function TrainingDatasetUploader({ files, onChange }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  async function addFiles(list: FileList | null) {
    if (!list) return;
    const picked = Array.from(list);
    const entries: DatasetFile[] = picked.map((f) => ({
      key: `${f.name}-${f.size}-${Math.random().toString(36).slice(2)}`,
      name: f.name,
      status: "uploading",
    }));
    onChange((prev) => [...prev, ...entries]);
    // One at a time — keeps the server's upload path (magic-byte sniff,
    // ffprobe, hashing) from being hammered by a big folder drop.
    for (let i = 0; i < picked.length; i++) {
      const key = entries[i].key;
      try {
        const res = await api.upload(picked[i]);
        onChange((prev) =>
          prev.map((f) =>
            f.key === key ? { ...f, status: "done", media_id: res.media_id, duration_sec: res.duration_sec } : f
          )
        );
      } catch (e) {
        const message = e instanceof ApiError ? translateError(e.code, e.message) : "업로드에 실패했습니다.";
        onChange((prev) => prev.map((f) => (f.key === key ? { ...f, status: "error", error: message } : f)));
      }
    }
  }

  const minutes = datasetMinutes(files);
  const quality = datasetQuality(minutes);
  const doneCount = files.filter((f) => f.status === "done").length;

  return (
    <div className="space-y-3">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          addFiles(e.dataTransfer.files);
        }}
        onClick={() => inputRef.current?.click()}
        className={`cursor-pointer rounded-lg border-2 border-dashed px-4 py-8 text-center transition-colors ${
          dragging ? "border-accent bg-accent/5" : "border-white/15 hover:border-white/30"
        }`}
      >
        <p className="text-sm">음원 파일을 여기로 끌어다 놓거나 클릭해서 선택하세요</p>
        <p className="mt-1 text-xs text-white/40">MP3 · WAV · M4A · FLAC, 여러 개 한 번에 가능 (파일당 최대 15분)</p>
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPT}
          multiple
          className="hidden"
          onChange={(e) => {
            addFiles(e.target.files);
            e.target.value = "";
          }}
        />
      </div>

      {files.length > 0 && (
        <ul className="divide-y divide-white/5 rounded-lg border border-white/10 bg-panel">
          {files.map((f) => (
            <li key={f.key} className="flex items-center gap-3 px-3 py-2 text-sm">
              <span className="w-4 text-center">
                {f.status === "uploading" ? (
                  <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-white/20 border-t-accent" />
                ) : f.status === "done" ? (
                  <span className="text-accent">✓</span>
                ) : (
                  <span className="text-red-400">!</span>
                )}
              </span>
              <span className="min-w-0 flex-1 truncate">{f.name}</span>
              <span className="shrink-0 text-xs text-white/40">
                {f.status === "done" && f.duration_sec != null
                  ? `${Math.floor(f.duration_sec / 60)}:${String(Math.round(f.duration_sec % 60)).padStart(2, "0")}`
                  : f.status === "error"
                    ? f.error
                    : "업로드 중…"}
              </span>
              {f.status !== "uploading" && (
                <button
                  type="button"
                  onClick={() => onChange((prev) => prev.filter((x) => x.key !== f.key))}
                  className="shrink-0 text-xs text-white/40 hover:text-red-400"
                  title="목록에서 빼기"
                >
                  ✕
                </button>
              )}
            </li>
          ))}
        </ul>
      )}

      {doneCount > 0 && (
        <div className="space-y-1">
          <div className="flex justify-between text-xs">
            <span className="text-white/60">
              총 {doneCount}개 · {minutes.toFixed(1)}분
            </span>
            <span className="text-white/50">{quality.label}</span>
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-white/10">
            <div className={`h-full ${quality.tone} transition-all`} style={{ width: `${quality.width}%` }} />
          </div>
        </div>
      )}
    </div>
  );
}
