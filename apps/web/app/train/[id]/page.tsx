"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ApiError, api, trainingDownloadUrl } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import { translateError } from "@/lib/errors";
import { TRAINING_STAGES, formatDuration, isActive, statusBadge } from "@/lib/training";
import type { TrainingJob, TrainingLog } from "@/lib/types";

const POLL_MS = 3000;
const EXTRA_PRESETS = [50, 100, 200];

export default function TrainingDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();

  const [job, setJob] = useState<TrainingJob | null>(null);
  const [log, setLog] = useState<TrainingLog | null>(null);
  const [showLog, setShowLog] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [extraEpochs, setExtraEpochs] = useState<number | null>(null);
  const [resumeBatch, setResumeBatch] = useState<number | null>(null);
  const logRef = useRef<HTMLPreElement>(null);

  const refresh = useCallback(async () => {
    try {
      setJob(await api.trainingGet(id));
    } catch (e) {
      setError(e instanceof ApiError ? translateError(e.code, e.message) : "불러오지 못했습니다.");
    }
  }, [id]);

  const refreshLog = useCallback(async () => {
    try {
      setLog(await api.trainingLog(id, 300));
    } catch {
      /* the log is a nice-to-have; the job card above is the source of truth */
    }
  }, [id]);

  useEffect(() => {
    if (authLoading || !user?.is_admin) return;
    refresh();
  }, [authLoading, user, refresh]);

  const active = job ? isActive(job) : false;
  useEffect(() => {
    if (!active) return;
    const t = setInterval(refresh, POLL_MS);
    return () => clearInterval(t);
  }, [active, refresh]);

  useEffect(() => {
    if (!showLog) return;
    refreshLog();
    if (!active) return;
    const t = setInterval(refreshLog, POLL_MS);
    return () => clearInterval(t);
  }, [showLog, active, refreshLog]);

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight });
  }, [log]);

  async function handleCancel() {
    if (
      !job ||
      !window.confirm("학습을 중지할까요? 마지막 체크포인트까지는 저장돼서, 나중에 그 지점부터 이어서 학습할 수 있어요.")
    )
      return;
    setBusy(true);
    try {
      setJob(await api.trainingCancel(job.job_id));
    } catch (e) {
      setError(e instanceof ApiError ? translateError(e.code, e.message) : "중지하지 못했습니다.");
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete() {
    if (
      !job ||
      !window.confirm(
        "학습 기록과 학습용 중간 파일(체크포인트 포함)을 삭제할까요? 삭제하면 더 이상 이어서 학습할 수 없어요. (이미 등록된 보이스 모델은 그대로 남아요)"
      )
    )
      return;
    setBusy(true);
    try {
      await api.trainingDelete(job.job_id);
      router.push("/train");
    } catch (e) {
      setError(e instanceof ApiError ? translateError(e.code, e.message) : "삭제하지 못했습니다.");
      setBusy(false);
    }
  }

  async function handleResume(extra: number) {
    if (!job) return;
    setBusy(true);
    setError(null);
    try {
      const next = await api.trainingResume(job.job_id, {
        extra_epochs: extra,
        ...(resumeBatch != null ? { batch_size: resumeBatch } : {}),
      });
      setJob(next);
      setExtraEpochs(null);
      setResumeBatch(null);
    } catch (e) {
      setError(e instanceof ApiError ? translateError(e.code, e.message) : "학습을 다시 시작하지 못했습니다.");
    } finally {
      setBusy(false);
    }
  }

  if (authLoading || (!job && !error)) return <p className="text-sm text-white/50">불러오는 중…</p>;
  if (!user?.is_admin) return <p className="text-sm text-white/50">관리자만 이용할 수 있습니다.</p>;
  if (!job) return <p className="text-sm text-red-400">{error}</p>;

  const badge = statusBadge(job);
  const stageIndex = TRAINING_STAGES.findIndex((s) => s.key === job.stage);
  const failed = job.status === "failed";
  const done = job.status === "succeeded";
  const reducedBatch = job.effective_batch_size != null && job.effective_batch_size < job.batch_size;
  const checkpoint = job.checkpoint_epoch ?? 0;
  // A stopped/failed run that hadn't reached its target: offer to finish it.
  const remaining = job.has_checkpoint && checkpoint < job.epochs ? job.epochs - checkpoint : null;
  const extra = extraEpochs ?? remaining ?? 100;
  const canRetry = !active && !job.has_checkpoint && failed;

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <a href="/train" className="text-xs text-white/40 hover:text-white/70">
          ← 보이스 학습
        </a>
        <div className="flex items-center gap-2">
          <h1 className="min-w-0 flex-1 truncate text-lg font-semibold">{job.name}</h1>
          <span className={`shrink-0 rounded px-2 py-0.5 text-xs ${badge.className}`}>{badge.text}</span>
        </div>
        <p className="text-xs text-white/50">
          {job.epochs} epoch · batch {job.batch_size} · {job.sample_rate} · 파일 {job.file_count}개
          {job.dataset_seconds != null && ` · 목소리 ${(job.dataset_seconds / 60).toFixed(1)}분`}
          {job.auto_vocal && " · 보컬 자동 추출"}
          {job.resume_count > 0 && ` · 이어서 학습 ${job.resume_count}회`}
        </p>
      </div>

      <ol className="grid grid-cols-5 gap-1">
        {TRAINING_STAGES.map((s, i) => {
          const state = done || i < stageIndex ? "done" : i === stageIndex ? (failed ? "failed" : "current") : "todo";
          return (
            <li key={s.key} className="space-y-1.5">
              <div
                className={`h-1 rounded-full ${
                  state === "done"
                    ? "bg-accent"
                    : state === "current"
                      ? "bg-accent/60 animate-pulse"
                      : state === "failed"
                        ? "bg-red-400"
                        : "bg-white/10"
                }`}
              />
              <p
                className={`text-[11px] leading-tight ${
                  state === "todo" ? "text-white/30" : state === "failed" ? "text-red-300" : "text-white/80"
                }`}
              >
                {s.label}
              </p>
            </li>
          );
        })}
      </ol>

      <div className="space-y-3 rounded-lg border border-white/10 bg-panel p-4">
        {job.status === "queued" && (
          <p className="text-sm text-white/60">
            대기 중이에요 — 지금 GPU에서 다른 작업(커버 만들기나 다른 학습)이 진행 중이면 그게 끝난 뒤 시작해요.
          </p>
        )}

        {job.status === "running" && (
          <>
            <div className="flex items-baseline justify-between gap-3">
              <p className="text-sm">
                {TRAINING_STAGES[stageIndex]?.label}
                <span className="ml-2 text-xs text-white/50">{TRAINING_STAGES[stageIndex]?.hint}</span>
              </p>
              <span className="text-sm text-white/60">{job.progress.toFixed(0)}%</span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-white/10">
              <div className="h-full bg-accent transition-all duration-500" style={{ width: `${job.progress}%` }} />
            </div>
            {job.stage === "train" && (
              <p className="text-xs text-white/60">
                Epoch {job.current_epoch} / {job.epochs}
                {job.eta_sec != null && job.current_epoch > 0 && ` · 남은 시간 약 ${formatDuration(job.eta_sec)}`}
                {job.current_epoch === 0 && " · 첫 epoch가 끝나면 남은 시간을 알려드려요"}
              </p>
            )}
            {reducedBatch && (
              <p className="text-xs text-amber-300/80">
                GPU 메모리가 부족해서 batch size를 {job.effective_batch_size}(으)로 자동 조정해 이어서 학습하고 있어요.
              </p>
            )}
            <p className="text-xs text-white/40">이 페이지를 닫아도 학습은 서버에서 계속 진행돼요.</p>
          </>
        )}

        {done && (
          <div className="space-y-3">
            <p className="text-sm">
              학습이 끝났어요! <span className="text-white/60">보이스 모델 목록에 &lsquo;{job.name}&rsquo;(으)로 등록됐습니다.</span>
            </p>
            <p className="text-xs text-white/50">
              {job.started_at &&
                job.finished_at &&
                `총 ${formatDuration((new Date(job.finished_at).getTime() - new Date(job.started_at).getTime()) / 1000)} 소요`}
              {reducedBatch && ` · batch size ${job.effective_batch_size}로 학습됨`}
            </p>
            {job.voice_model_id && (
              <a
                href={`/?voice=${job.voice_model_id}`}
                className="inline-block rounded-md bg-accent px-4 py-2 text-sm font-medium text-ink"
              >
                이 목소리로 커버 만들기 →
              </a>
            )}
          </div>
        )}

        {failed && (
          <div className="space-y-2">
            <p className="text-sm text-red-300">
              {job.error_code === "CANCELLED" ? "학습을 중지했어요." : translateError(job.error_code, null)}
            </p>
            {job.error_code !== "CANCELLED" && job.error_message && (
              <pre className="max-h-40 overflow-auto whitespace-pre-wrap rounded bg-ink p-2 text-[11px] text-white/50">
                {job.error_message}
              </pre>
            )}
          </div>
        )}
      </div>

      {job.has_model_file && (
        <div className="space-y-3 rounded-lg border border-white/10 bg-panel p-4">
          <div>
            <p className="text-sm font-medium">모델 파일</p>
            <p className="mt-0.5 text-xs text-white/50">
              {active
                ? "지금 받으면 이전까지 학습된 버전이에요. 학습이 끝나면 새 버전으로 바뀌어요."
                : "RVC WebUI 등 다른 RVC 프로그램에서도 그대로 쓸 수 있어요."}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <a
              href={trainingDownloadUrl(job.job_id, "zip")}
              download
              className="rounded-md bg-white/10 px-3 py-1.5 text-sm hover:bg-white/15"
            >
              ⬇ 모델 + 인덱스 (.zip)
            </a>
            <a
              href={trainingDownloadUrl(job.job_id, "weight")}
              download
              className="px-2 py-1.5 text-xs text-white/50 hover:text-white/80"
            >
              .pth만
            </a>
            <a
              href={trainingDownloadUrl(job.job_id, "index")}
              download
              className="px-2 py-1.5 text-xs text-white/50 hover:text-white/80"
            >
              .index만
            </a>
          </div>
        </div>
      )}

      {!active && job.has_checkpoint && (
        <div className="space-y-3 rounded-lg border border-white/10 bg-panel p-4">
          <div>
            <p className="text-sm font-medium">이어서 학습</p>
            <p className="mt-0.5 text-xs text-white/50">
              저장된 체크포인트(epoch {checkpoint})부터 이어서 학습해요. 데이터 준비·전처리는 건너뛰고, 끝나면 등록된
              모델이 새 버전으로 바뀌어요.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {remaining != null && (
              <button
                type="button"
                onClick={() => setExtraEpochs(remaining)}
                className={`rounded-md border px-3 py-1.5 text-xs ${
                  extra === remaining ? "border-accent bg-accent/10 text-accent" : "border-white/10 text-white/70"
                }`}
              >
                남은 {remaining} epoch 마저 하기
              </button>
            )}
            {EXTRA_PRESETS.map((n) => (
              <button
                key={n}
                type="button"
                onClick={() => setExtraEpochs(n)}
                className={`rounded-md border px-3 py-1.5 text-xs ${
                  extra === n ? "border-accent bg-accent/10 text-accent" : "border-white/10 text-white/70"
                }`}
              >
                +{n} epoch
              </button>
            ))}
            <input
              type="number"
              min={1}
              max={1000}
              value={extra}
              onChange={(e) => setExtraEpochs(Number(e.target.value))}
              className="w-24 rounded-md border border-white/10 bg-ink px-2 py-1.5 text-xs outline-none focus:border-accent"
              title="추가할 epoch 수 (1~1000)"
            />
          </div>
          <div className="flex flex-wrap items-center gap-3 text-xs text-white/60">
            <span>
              총 {checkpoint + extra} epoch까지
            </span>
            <label className="flex items-center gap-1.5">
              batch size
              <input
                type="number"
                min={1}
                max={16}
                value={resumeBatch ?? job.effective_batch_size ?? job.batch_size}
                onChange={(e) => setResumeBatch(Number(e.target.value))}
                className="w-14 rounded-md border border-white/10 bg-ink px-2 py-1 outline-none focus:border-accent"
              />
            </label>
          </div>
          <button
            onClick={() => handleResume(extra)}
            disabled={busy || !(extra >= 1 && extra <= 1000)}
            className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-ink disabled:opacity-40"
          >
            이어서 학습 시작
          </button>
        </div>
      )}

      {canRetry && (
        <div className="flex flex-wrap items-center gap-3 rounded-lg border border-white/10 bg-panel p-4">
          <p className="min-w-0 flex-1 text-xs text-white/60">
            저장된 체크포인트가 없어서 같은 설정으로 처음부터 다시 학습해요.
          </p>
          <button
            onClick={() => handleResume(job.epochs)}
            disabled={busy}
            className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-ink disabled:opacity-40"
          >
            다시 시도
          </button>
        </div>
      )}

      {error && <p className="text-sm text-red-400">{error}</p>}

      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => setShowLog((v) => !v)}
          className="rounded-md border border-white/10 px-3 py-1.5 text-xs hover:border-white/30"
        >
          {showLog ? "로그 숨기기" : "상세 로그 보기"}
        </button>
        {active ? (
          <button
            onClick={handleCancel}
            disabled={busy}
            className="rounded-md border border-white/10 px-3 py-1.5 text-xs hover:border-red-400 hover:text-red-400 disabled:opacity-40"
          >
            학습 중지
          </button>
        ) : (
          <button
            onClick={handleDelete}
            disabled={busy}
            className="rounded-md border border-white/10 px-3 py-1.5 text-xs hover:border-red-400 hover:text-red-400 disabled:opacity-40"
          >
            기록 삭제
          </button>
        )}
      </div>

      {showLog && (
        <pre
          ref={logRef}
          className="max-h-80 overflow-auto whitespace-pre-wrap rounded-lg border border-white/10 bg-black/40 p-3 font-mono text-[11px] leading-relaxed text-white/60"
        >
          {log?.lines.length ? log.lines.join("\n") : "아직 로그가 없어요."}
        </pre>
      )}
    </div>
  );
}
