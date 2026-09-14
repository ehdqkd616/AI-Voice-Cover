"use client";

import type { CoverRequest, F0Method, OutputFormat, SeparationEngine, SeparationQuality } from "@/lib/types";

export type ConversionParams = Omit<CoverRequest, "media_id" | "youtube_url" | "voice_model_id">;

export const DEFAULT_CONVERSION_PARAMS: ConversionParams = {
  f0_up_key: 0,
  f0_method: "rmvpe",
  index_rate: 0.75,
  protect: 0.33,
  rms_mix_rate: 0.25,
  output_format: "mp3-320",
  vocal_gain_db: 0,
  quality: "fast",
  separation_engine: "demucs",
  instrumental_pitch: 0,
};

interface Props {
  value: ConversionParams;
  onChange: (v: ConversionParams) => void;
}

const F0_METHODS: F0Method[] = ["pm", "rmvpe", "fcpe"];
const OUTPUT_FORMATS: OutputFormat[] = ["mp3-320", "wav"];
const QUALITIES: { value: SeparationQuality; label: string }[] = [
  { value: "fast", label: "빠름" },
  { value: "high", label: "고품질" },
];
const SEPARATION_ENGINES: { value: SeparationEngine; label: string }[] = [
  { value: "demucs", label: "Demucs" },
  { value: "mdx_net", label: "UVR-MDX-NET (보컬 특화)" },
];

export default function ConversionParamsForm({ value, onChange }: Props) {
  function set<K extends keyof ConversionParams>(key: K, v: ConversionParams[K]) {
    onChange({ ...value, [key]: v });
  }

  return (
    <div className="space-y-5">
      <div className="space-y-1">
        <label className="text-sm font-medium">피치 조절 (semitones)</label>
        <p className="text-white/50 text-xs">부르는 사람의 음역대에 맞게 키를 조절하세요 (반음 단위)</p>
        <input
          type="number"
          min={-24}
          max={24}
          value={value.f0_up_key}
          onChange={(e) => set("f0_up_key", Number(e.target.value))}
          className="w-28 rounded-md bg-panel border border-white/10 px-3 py-2 text-sm outline-none focus:border-accent"
        />
      </div>

      <div className="space-y-1">
        <label className="text-sm font-medium">반주(MR) 피치 조절</label>
        <p className="text-white/50 text-xs">보컬 피치와는 별개로 반주 자체의 키를 바꿉니다 (템포는 유지)</p>
        <input
          type="number"
          min={-24}
          max={24}
          value={value.instrumental_pitch}
          onChange={(e) => set("instrumental_pitch", Number(e.target.value))}
          className="w-28 rounded-md bg-panel border border-white/10 px-3 py-2 text-sm outline-none focus:border-accent"
        />
      </div>

      <div className="space-y-1">
        <label className="text-sm font-medium">보컬/반주 분리 엔진</label>
        <p className="text-white/50 text-xs">UVR-MDX-NET은 보컬 분리 정확도가 높은 편이지만 CPU로 처리되어 더 느립니다</p>
        <div className="flex gap-2">
          {SEPARATION_ENGINES.map((e) => (
            <button
              key={e.value}
              type="button"
              onClick={() => set("separation_engine", e.value)}
              className={`rounded-md border px-3 py-1.5 text-xs ${
                value.separation_engine === e.value
                  ? "border-accent text-accent bg-accent/10"
                  : "border-white/10 text-white/70 hover:border-white/30"
              }`}
            >
              {e.label}
            </button>
          ))}
        </div>
      </div>

      {value.separation_engine === "demucs" && (
        <div className="space-y-1">
          <label className="text-sm font-medium">보컬/반주 분리 품질</label>
          <p className="text-white/50 text-xs">고품질은 더 정확하지만 처리 시간이 더 걸립니다</p>
          <div className="flex gap-2">
            {QUALITIES.map((q) => (
              <button
                key={q.value}
                type="button"
                onClick={() => set("quality", q.value)}
                className={`rounded-md border px-3 py-1.5 text-xs ${
                  value.quality === q.value
                    ? "border-accent text-accent bg-accent/10"
                    : "border-white/10 text-white/70 hover:border-white/30"
                }`}
              >
                {q.label}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="space-y-1">
        <label className="text-sm font-medium">피치 추출 방식 (f0_method)</label>
        <p className="text-white/50 text-xs">rmvpe를 권장합니다</p>
        <div className="flex gap-2">
          {F0_METHODS.map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => set("f0_method", m)}
              className={`rounded-md border px-3 py-1.5 text-xs ${
                value.f0_method === m
                  ? "border-accent text-accent bg-accent/10"
                  : "border-white/10 text-white/70 hover:border-white/30"
              }`}
            >
              {m}
            </button>
          ))}
        </div>
      </div>

      <div className="space-y-1">
        <label className="text-sm font-medium">인덱스 반영 비율 (index_rate)</label>
        <p className="text-white/50 text-xs">원본 보이스의 음색을 얼마나 강하게 반영할지</p>
        <div className="flex items-center gap-3">
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={value.index_rate}
            onChange={(e) => set("index_rate", Number(e.target.value))}
            className="flex-1"
          />
          <span className="text-xs text-white/50 w-10 text-right">{value.index_rate.toFixed(2)}</span>
        </div>
      </div>

      <div className="space-y-1">
        <label className="text-sm font-medium">보호 강도 (protect)</label>
        <p className="text-white/50 text-xs">자음/숨소리 보호 강도 — 높을수록 원음 보존</p>
        <div className="flex items-center gap-3">
          <input
            type="range"
            min={0}
            max={0.5}
            step={0.01}
            value={value.protect}
            onChange={(e) => set("protect", Number(e.target.value))}
            className="flex-1"
          />
          <span className="text-xs text-white/50 w-10 text-right">{value.protect.toFixed(2)}</span>
        </div>
      </div>

      <div className="space-y-1">
        <label className="text-sm font-medium">라우드니스 믹스 비율 (rms_mix_rate)</label>
        <div className="flex items-center gap-3">
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={value.rms_mix_rate}
            onChange={(e) => set("rms_mix_rate", Number(e.target.value))}
            className="flex-1"
          />
          <span className="text-xs text-white/50 w-10 text-right">{value.rms_mix_rate.toFixed(2)}</span>
        </div>
      </div>

      <div className="space-y-1">
        <label className="text-sm font-medium">보컬 볼륨 보정 (vocal_gain_db)</label>
        <p className="text-white/50 text-xs">최종 믹스에서 보컬 볼륨을 dB 단위로 조절</p>
        <input
          type="number"
          min={-12}
          max={12}
          value={value.vocal_gain_db}
          onChange={(e) => set("vocal_gain_db", Number(e.target.value))}
          className="w-28 rounded-md bg-panel border border-white/10 px-3 py-2 text-sm outline-none focus:border-accent"
        />
      </div>

      <div className="space-y-1">
        <label className="text-sm font-medium">출력 형식 (output_format)</label>
        <div className="flex gap-2">
          {OUTPUT_FORMATS.map((f) => (
            <button
              key={f}
              type="button"
              onClick={() => set("output_format", f)}
              className={`rounded-md border px-3 py-1.5 text-xs ${
                value.output_format === f
                  ? "border-accent text-accent bg-accent/10"
                  : "border-white/10 text-white/70 hover:border-white/30"
              }`}
            >
              {f}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
