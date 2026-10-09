"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import TrainingDatasetUploader, { DatasetFile, datasetMinutes } from "@/components/TrainingDatasetUploader";
import { ApiError, api } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import { translateError } from "@/lib/errors";
import { PRESETS, formatDuration, isActive, stageLabel, statusBadge } from "@/lib/training";
import type { TrainingJob } from "@/lib/types";

type PresetKey = (typeof PRESETS)[number]["key"] | "custom";

export default function TrainPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [files, setFiles] = useState<DatasetFile[]>([]);
  const [autoVocal, setAutoVocal] = useState(true);
  const [preset, setPreset] = useState<PresetKey>("standard");
  const [customEpochs, setCustomEpochs] = useState(300);
  const [batchSize, setBatchSize] = useState(2);
  const [sampleRate, setSampleRate] = useState<"40k" | "48k">("40k");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [jobs, setJobs] = useState<TrainingJob[] | null>(null);

  const loadJobs = useCallback(() => {
    api
      .trainingList()
      .then(setJobs)
      .catch(() => setJobs((prev) => prev ?? []));
  }, []);

  useEffect(() => {
    if (authLoading || !user?.is_admin) return;
    loadJobs();
  }, [authLoading, user, loadJobs]);

  // Keep the history list fresh while anything is still running.
  useEffect(() => {
    if (!jobs?.some(isActive)) return;
    const t = setInterval(loadJobs, 5000);
    return () => clearInterval(t);
  }, [jobs, loadJobs]);

  const epochs = preset === "custom" ? customEpochs : PRESETS.find((p) => p.key === preset)!.epochs;
  const uploading = files.some((f) => f.status === "uploading");
  const mediaIds = files.filter((f) => f.status === "done" && f.media_id).map((f) => f.media_id!);
  const minutes = datasetMinutes(files);
  const canSubmit = name.trim().length > 0 && mediaIds.length > 0 && minutes >= 1 && !uploading && !submitting;

  async function handleSubmit() {
    if (!canSubmit) return;
    setSubmitting(true);
    setError(null);
    try {
      const job = await api.trainingStart({
        name: name.trim(),
        description: description.trim() || undefined,
        media_ids: mediaIds,
        auto_vocal: autoVocal,
        epochs,
        batch_size: batchSize,
        sample_rate: sampleRate,
      });
      router.push(`/train/${job.job_id}`);
    } catch (e) {
      setError(e instanceof ApiError ? translateError(e.code, e.message) : "학습을 시작하지 못했습니다.");
      setSubmitting(false);
    }
  }

  if (authLoading) return <p className="text-sm text-white/50">불러오는 중…</p>;
  if (!user || !user.is_admin) {
    return (
      <div className="space-y-4">
        <h1 className="text-lg font-semibold">보이스 학습</h1>
        <p className="text-sm text-white/50">{user ? "관리자만 이용할 수 있습니다." : "로그인이 필요합니다."}</p>
      </div>
    );
  }

  return (
    <div className="space-y-10">
      <section className="space-y-6">
        <div>
          <h1 className="text-lg font-semibold">새 보이스 모델 만들기</h1>
          <p className="mt-1 text-sm text-white/50">
            목소리가 담긴 음원만 올리면 나머지(보컬 추출 · 전처리 · 학습 · 인덱스 · 모델 등록)는 자동으로 진행돼요.
          </p>
        </div>

        <Step n={1} title="모델 이름">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            maxLength={40}
            placeholder="예: 내 목소리, 박효신 2020"
            className="w-full rounded-md border border-white/10 bg-panel px-3 py-2 text-sm outline-none focus:border-accent"
          />
          <input
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            maxLength={200}
            placeholder="설명 (선택)"
            className="w-full rounded-md border border-white/10 bg-panel px-3 py-2 text-sm outline-none focus:border-accent"
          />
        </Step>

        <Step n={2} title="학습할 목소리">
          <TrainingDatasetUploader files={files} onChange={setFiles} />
          <label className="flex cursor-pointer items-start gap-3 rounded-lg border border-white/10 bg-panel p-3">
            <input
              type="checkbox"
              checked={autoVocal}
              onChange={(e) => setAutoVocal(e.target.checked)}
              className="mt-0.5 accent-[#6ee7b7]"
            />
            <span className="text-sm">
              보컬 자동 추출
              <span className="mt-0.5 block text-xs text-white/50">
                반주가 섞인 노래 원곡도 그대로 올려도 돼요. 이미 반주 없는 목소리만 있는 파일이라면 꺼도 됩니다.
              </span>
            </span>
          </label>
          <details className="text-xs text-white/50">
            <summary className="cursor-pointer select-none hover:text-white/70">좋은 학습 데이터 팁</summary>
            <ul className="mt-2 list-disc space-y-1 pl-5">
              <li>한 사람의 목소리만 — 다른 가수·코러스·대화 상대가 섞이지 않게</li>
              <li>총 10~30분이 적당해요. 길수록 좋지만 학습 시간도 늘어나요</li>
              <li>잡음·울림(리버브)이 적고 또렷한 녹음일수록 결과가 깨끗해요</li>
              <li>다양한 음높이(저음~고음)가 들어 있으면 변환 범위가 넓어져요</li>
            </ul>
          </details>
        </Step>

        <Step n={3} title="학습 강도">
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
            {PRESETS.map((p) => (
              <button
                key={p.key}
                type="button"
                onClick={() => setPreset(p.key)}
                className={`rounded-lg border p-3 text-left transition-colors ${
                  preset === p.key ? "border-accent bg-accent/10" : "border-white/10 bg-panel hover:border-white/30"
                }`}
              >
                <p className="text-sm font-medium">
                  {p.label}
                  {"recommended" in p && p.recommended && (
                    <span className="ml-1.5 rounded bg-accent/20 px-1.5 py-0.5 text-[10px] text-accent">추천</span>
                  )}
                </p>
                <p className="mt-0.5 text-xs text-white/50">
                  {p.epochs} epoch · {p.desc}
                </p>
              </button>
            ))}
          </div>

          <button
            type="button"
            onClick={() => setShowAdvanced((v) => !v)}
            className="text-xs text-white/50 hover:text-white/80"
          >
            {showAdvanced ? "▾" : "▸"} 고급 설정
          </button>
          {showAdvanced && (
            <div className="grid grid-cols-1 gap-4 rounded-lg border border-white/10 bg-panel p-4 sm:grid-cols-3">
              <label className="space-y-1 text-sm">
                <span className="block">Epoch 수</span>
                <input
                  type="number"
                  min={10}
                  max={1000}
                  value={preset === "custom" ? customEpochs : epochs}
                  onChange={(e) => {
                    setPreset("custom");
                    setCustomEpochs(Number(e.target.value));
                  }}
                  className="w-full rounded-md border border-white/10 bg-ink px-3 py-1.5 outline-none focus:border-accent"
                />
                <span className="block text-xs text-white/40">10~1000. 많을수록 정교하지만 오래 걸려요</span>
              </label>
              <label className="space-y-1 text-sm">
                <span className="block">Batch size</span>
                <input
                  type="number"
                  min={1}
                  max={16}
                  value={batchSize}
                  onChange={(e) => setBatchSize(Number(e.target.value))}
                  className="w-full rounded-md border border-white/10 bg-ink px-3 py-1.5 outline-none focus:border-accent"
                />
                <span className="block text-xs text-white/40">GPU 메모리가 부족하면 자동으로 줄여서 이어 학습해요</span>
              </label>
              <div className="space-y-1 text-sm">
                <span className="block">샘플레이트</span>
                <div className="flex gap-2">
                  {(["40k", "48k"] as const).map((sr) => (
                    <button
                      key={sr}
                      type="button"
                      onClick={() => setSampleRate(sr)}
                      className={`rounded-md border px-3 py-1.5 text-xs ${
                        sampleRate === sr ? "border-accent bg-accent/10 text-accent" : "border-white/10 text-white/70"
                      }`}
                    >
                      {sr}
                    </button>
                  ))}
                </div>
                <span className="block text-xs text-white/40">40k 권장. 48k는 원본 음질이 아주 좋을 때만</span>
              </div>
            </div>
          )}
        </Step>

        {error && <p className="text-sm text-red-400">{error}</p>}
        <div className="space-y-2">
          <button
            onClick={handleSubmit}
            disabled={!canSubmit}
            className="w-full rounded-md bg-accent px-4 py-2.5 text-sm font-medium text-ink disabled:opacity-40"
          >
            {submitting ? "시작하는 중…" : uploading ? "업로드가 끝나면 시작할 수 있어요" : "학습 시작"}
          </button>
          <p className="text-center text-xs text-white/40">
            학습은 GPU를 쓰기 때문에, 학습 중에 요청한 커버 만들기는 학습이 끝날 때까지 대기열에서 기다려요.
          </p>
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-sm font-medium text-white/80">학습 기록</h2>
        {jobs === null && <p className="text-sm text-white/50">불러오는 중…</p>}
        {jobs?.length === 0 && <p className="text-sm text-white/40">아직 학습한 모델이 없어요.</p>}
        <div className="space-y-2">
          {jobs?.map((job) => {
            const badge = statusBadge(job);
            return (
              <a
                key={job.job_id}
                href={`/train/${job.job_id}`}
                className="block rounded-lg border border-white/10 bg-panel p-3 hover:border-white/25"
              >
                <div className="flex items-center gap-2">
                  <p className="min-w-0 flex-1 truncate text-sm font-medium">{job.name}</p>
                  <span className={`shrink-0 rounded px-2 py-0.5 text-[11px] ${badge.className}`}>{badge.text}</span>
                </div>
                <p className="mt-1 text-xs text-white/50">
                  {job.status === "running"
                    ? job.stage === "train"
                      ? `Epoch ${job.current_epoch}/${job.epochs} · 남은 시간 약 ${formatDuration(job.eta_sec)}`
                      : `${stageLabel(job.stage)} 중`
                    : `${job.epochs} epoch · 파일 ${job.file_count}개 · ${new Date(job.queued_at).toLocaleString("ko-KR")}`}
                </p>
                {isActive(job) && (
                  <div className="mt-2 h-1 overflow-hidden rounded-full bg-white/10">
                    <div className="h-full bg-accent transition-all" style={{ width: `${job.progress}%` }} />
                  </div>
                )}
              </a>
            );
          })}
        </div>
      </section>
    </div>
  );
}

function Step({ n, title, children }: { n: number; title: string; children: React.ReactNode }) {
  return (
    <div className="space-y-3">
      <h2 className="flex items-center gap-2 text-sm font-medium">
        <span className="flex h-5 w-5 items-center justify-center rounded-full bg-white/10 text-[11px]">{n}</span>
        {title}
      </h2>
      <div className="space-y-3 pl-7">{children}</div>
    </div>
  );
}
