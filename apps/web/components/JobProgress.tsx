"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api-client";
import { translateError } from "@/lib/errors";

interface Props {
  jobId: string;
  onComplete: (outputs: string[]) => void;
  onError?: (message: string) => void;
}

const STAGE_LABEL: Record<string, string> = {
  downloading: "원곡 다운로드 중",
  separating: "보컬/반주 분리 중",
  converting: "보이스 변환 중",
  mixing: "믹싱 중",
};

export default function JobProgress({ jobId, onComplete, onError }: Props) {
  const [stage, setStage] = useState("queued");
  const [percent, setPercent] = useState(0);
  const doneRef = useRef(false);

  useEffect(() => {
    doneRef.current = false;
    const source = new EventSource(api.jobEventsUrl(jobId));

    source.addEventListener("progress", (e) => {
      const data = JSON.parse((e as MessageEvent).data);
      setStage(data.stage ?? "processing");
      setPercent(data.percent ?? 0);
    });

    source.addEventListener("complete", (e) => {
      if (doneRef.current) return;
      doneRef.current = true;
      const data = JSON.parse((e as MessageEvent).data);
      const outputs: string[] = (data.outputs ?? []).map((o: { media_id: string }) => o.media_id);
      setPercent(100);
      source.close();
      onComplete(outputs);
    });

    source.addEventListener("error", (e) => {
      if (doneRef.current) return;
      doneRef.current = true;
      const data = (e as MessageEvent).data ? JSON.parse((e as MessageEvent).data) : {};
      source.close();
      onError?.(translateError(data.code, data.message));
    });

    return () => source.close();
  }, [jobId, onComplete, onError]);

  return (
    <div className="rounded-lg border border-white/10 bg-panel p-4">
      <div className="flex items-center justify-between text-sm mb-2">
        <span>{STAGE_LABEL[stage] ?? stage}</span>
        <span className="text-white/50">{percent.toFixed(0)}%</span>
      </div>
      <div className="h-2 rounded-full bg-white/10 overflow-hidden">
        <div
          className="h-full bg-accent transition-all duration-300"
          style={{ width: `${Math.min(percent, 100)}%` }}
        />
      </div>
    </div>
  );
}
