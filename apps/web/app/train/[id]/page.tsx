"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ApiError, api } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import { translateError } from "@/lib/errors";
import { TRAINING_STAGES, formatDuration, isActive, statusBadge } from "@/lib/training";
import type { TrainingJob, TrainingLog } from "@/lib/types";

const POLL_MS = 3000;

export default function TrainingDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();

  const [job, setJob] = useState<TrainingJob | null>(null);
  const [log, setLog] = useState<TrainingLog | null>(null);
  const [showLog, setShowLog] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
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
    if (!job || !window.confirm("학습을 중지할까요? 지금까지의 학습 결과는 저장되지 않아요.")) return;
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
    if (!job || !window.confirm("학습 기록과 학습용 중간 파일을 삭제할까요? (이미 등록된 보이스 모델은 그대로 남아요)")) return;
    setBusy(true);
    try {
      await api.trainingDelete(job.job_id);
      router.push("/train");
    } catch (e) {
      setError(e instanceof ApiError ? translateError(e.code, e.message) : "삭제하지 못했습니다.");
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
