"use client";

import { useEffect, useState } from "react";
import { ApiError, api } from "@/lib/api-client";
import { translateError } from "@/lib/errors";
import type { VoiceModel } from "@/lib/types";

interface Props {
  selected: string | null;
  onSelect: (voiceModelId: string) => void;
}

export default function VoiceModelPicker({ selected, onSelect }: Props) {
  const [models, setModels] = useState<VoiceModel[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .voiceModels()
      .then(setModels)
      .catch((e) =>
        setError(e instanceof ApiError ? translateError(e.code, e.message) : "보이스 모델을 불러오지 못했습니다.")
      );
  }, []);

  if (error) return <p className="text-sm text-red-400">{error}</p>;

  if (models === null) return <p className="text-sm text-white/50">불러오는 중…</p>;

  if (models.length === 0) {
    return <p className="text-sm text-white/50">등록된 보이스 모델이 없습니다. 관리자에게 문의하세요.</p>;
  }

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
      {models.map((m) => (
        <button
          key={m.id}
          type="button"
          onClick={() => onSelect(m.id)}
          className={`text-left rounded-lg border p-3 space-y-1 ${
            selected === m.id ? "border-accent bg-accent/10" : "border-white/10 bg-panel hover:border-white/30"
          }`}
        >
          <p className="text-sm font-medium truncate">{m.name}</p>
          {m.description && <p className="text-xs text-white/50 line-clamp-2">{m.description}</p>}
          {/* "manual"/"auto_high" both have a correctly-paired index — no badge needed.
              "auto_low" has an index too, just an uncertain auto-match; "unpaired" truly
              has none. Conflating all three into one "미매칭" label (as an earlier version
              of this component did) wrongly flagged auto_high models that are perfectly fine. */}
          {m.pairing_confidence === "auto_low" && (
            <span className="inline-block rounded-md bg-amber-400/10 text-amber-300 text-[11px] px-2 py-0.5">
              인덱스 매칭 확인 필요
            </span>
          )}
          {m.pairing_confidence === "unpaired" && (
            <span className="inline-block rounded-md bg-red-400/10 text-red-300 text-[11px] px-2 py-0.5">
              인덱스 없음
            </span>
          )}
        </button>
      ))}
    </div>
  );
}
