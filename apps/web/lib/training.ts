import type { TrainingJob, TrainingStage } from "./types";

export const TRAINING_STAGES: { key: TrainingStage; label: string; hint: string }[] = [
  { key: "prepare", label: "데이터 준비", hint: "음원을 내려받고 보컬만 추출해요" },
  { key: "preprocess", label: "전처리", hint: "목소리를 짧은 구간으로 자르고 정리해요" },
  { key: "extract", label: "특징 추출", hint: "음정과 음색 특징을 뽑아내요" },
  { key: "train", label: "모델 학습", hint: "목소리를 학습해요 — 가장 오래 걸리는 단계" },
  { key: "index", label: "인덱스 생성", hint: "음색 검색 인덱스를 만들고 모델을 등록해요" },
];

export const PRESETS = [
  { key: "quick", label: "빠른 테스트", epochs: 50, desc: "결과를 빨리 확인해보고 싶을 때" },
  { key: "standard", label: "표준", epochs: 200, desc: "대부분의 경우 추천", recommended: true },
  { key: "high", label: "고품질", epochs: 400, desc: "데이터가 충분하고 시간이 넉넉할 때" },
] as const;

export function isActive(job: Pick<TrainingJob, "status">): boolean {
  return job.status === "queued" || job.status === "running";
}

export function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null || !Number.isFinite(seconds)) return "-";
  const s = Math.max(0, Math.round(seconds));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  if (h > 0) return `${h}시간 ${m}분`;
  if (m > 0) return `${m}분 ${s % 60}초`;
  return `${s}초`;
}

export function statusBadge(job: TrainingJob): { text: string; className: string } {
  if (job.status === "succeeded") return { text: "완료", className: "bg-accent/15 text-accent" };
  if (job.status === "running") return { text: "학습 중", className: "bg-sky-400/15 text-sky-300" };
  if (job.status === "queued") return { text: "대기 중", className: "bg-white/10 text-white/60" };
  if (job.error_code === "CANCELLED") return { text: "중지됨", className: "bg-white/10 text-white/50" };
  return { text: "실패", className: "bg-red-400/15 text-red-300" };
}

export function stageLabel(stage: TrainingStage): string {
  return TRAINING_STAGES.find((s) => s.key === stage)?.label ?? stage;
}
