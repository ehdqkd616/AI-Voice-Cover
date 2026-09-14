"use client";

import { useState } from "react";
import ConversionParamsForm, {
  ConversionParams,
  DEFAULT_CONVERSION_PARAMS,
} from "@/components/ConversionParamsForm";
import JobProgress from "@/components/JobProgress";
import ResultPlayer from "@/components/ResultPlayer";
import SourcePicker, { SourceInput } from "@/components/SourcePicker";
import VoiceModelPicker from "@/components/VoiceModelPicker";
import { ApiError, api } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import { translateError } from "@/lib/errors";
import type { CoverRequest } from "@/lib/types";

type Step = "source" | "configure" | "running" | "done" | "error";

export default function HomePage() {
  const { user, loading: authLoading } = useAuth();

  const [step, setStep] = useState<Step>("source");
  const [source, setSource] = useState<SourceInput | null>(null);
  const [voiceModelId, setVoiceModelId] = useState<string | null>(null);
  const [params, setParams] = useState<ConversionParams>(DEFAULT_CONVERSION_PARAMS);
  const [submitting, setSubmitting] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [finalMediaId, setFinalMediaId] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  function reset() {
    setStep("source");
    setSource(null);
    setVoiceModelId(null);
    setParams(DEFAULT_CONVERSION_PARAMS);
    setJobId(null);
    setFinalMediaId(null);
    setErrorMessage(null);
  }

  async function handleSubmit() {
    if (!source || !voiceModelId) return;
    setSubmitting(true);
    setErrorMessage(null);
    try {
      const body: CoverRequest = {
        ...(source.kind === "media" ? { media_id: source.media_id } : { youtube_url: source.youtube_url }),
        voice_model_id: voiceModelId,
        ...params,
      };
      const res = await api.createCover(body);
      setJobId(res.job_id);
      setStep("running");
    } catch (e) {
      setErrorMessage(e instanceof ApiError ? translateError(e.code, e.message) : "요청에 실패했습니다.");
      setStep("error");
    } finally {
      setSubmitting(false);
    }
  }

  if (authLoading) return <p className="text-sm text-white/50">불러오는 중…</p>;

  if (!user) {
    return (
      <div className="space-y-4">
        <h1 className="text-lg font-semibold">AI 보이스 커버 만들기</h1>
        <p className="text-sm text-white/50">로그인이 필요합니다.</p>
        <a href="/login" className="inline-block rounded-md bg-accent text-ink font-medium px-4 py-2 text-sm">
          로그인
        </a>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-lg font-semibold">AI 보이스 커버 만들기</h1>

      {step === "source" && (
        <SourcePicker
          onReady={(input) => {
            setSource(input);
            setStep("configure");
          }}
        />
      )}

      {step === "configure" && source && (
        <div className="space-y-6">
          <div className="rounded-lg border border-white/10 bg-panel p-3 flex items-center justify-between gap-3">
            <p className="text-sm truncate">
              {source.kind === "media" ? source.title ?? "업로드한 파일" : `유튜브 영상 · ${source.title}`}
            </p>
            <button
              onClick={() => setStep("source")}
              className="text-xs text-white/50 hover:text-white whitespace-nowrap"
            >
              다시 선택
            </button>
          </div>

          <div className="space-y-2">
            <h2 className="text-sm font-medium">보이스 모델 선택</h2>
            <VoiceModelPicker selected={voiceModelId} onSelect={setVoiceModelId} />
          </div>

          <div className="space-y-2">
            <h2 className="text-sm font-medium">변환 설정</h2>
            <ConversionParamsForm value={params} onChange={setParams} />
          </div>

          {errorMessage && <p className="text-sm text-red-400">{errorMessage}</p>}

          <div className="flex gap-2">
            <button
              onClick={() => setStep("source")}
              className="rounded-md border border-white/10 hover:border-white/30 px-4 py-2 text-sm"
            >
              뒤로
            </button>
            <button
              onClick={handleSubmit}
              disabled={!voiceModelId || submitting}
              className="flex-1 rounded-md bg-accent text-ink font-medium px-4 py-2 text-sm disabled:opacity-50"
            >
              {submitting ? "요청 중…" : "커버 만들기"}
            </button>
          </div>
        </div>
      )}

      {step === "running" && jobId && (
        <JobProgress
          jobId={jobId}
          onComplete={(outputs) => {
            setFinalMediaId(outputs[0] ?? null);
            setStep("done");
          }}
          onError={(message) => {
            setErrorMessage(message);
            setStep("error");
          }}
        />
      )}

      {step === "done" && finalMediaId && (
        <div className="space-y-4">
          <ResultPlayer mediaId={finalMediaId} />
          <button
            onClick={reset}
            className="rounded-md border border-white/10 hover:border-white/30 px-4 py-2 text-sm"
          >
            다시 만들기
          </button>
        </div>
      )}

      {step === "error" && (
        <div className="space-y-4">
          <p className="text-sm text-red-400">{errorMessage ?? "작업이 실패했습니다."}</p>
          <button
            onClick={() => setStep("configure")}
            className="rounded-md bg-accent text-ink font-medium px-4 py-2 text-sm"
          >
            다시 시도
          </button>
        </div>
      )}
    </div>
  );
}
