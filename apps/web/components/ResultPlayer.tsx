"use client";

import { mediaStreamUrl, mediaDownloadUrl } from "@/lib/api-client";

interface Props {
  mediaId: string;
}

export default function ResultPlayer({ mediaId }: Props) {
  return (
    <div className="space-y-3 rounded-lg border border-white/10 bg-panel p-4">
      {/* Proxied through the API (not a presigned MinIO URL) — this deployment
          only exposes the API's own domain publicly, and <audio src>/<a href>
          both send the session cookie automatically for same-origin requests,
          so no separate fetch-then-set-url step is needed. */}
      {/* eslint-disable-next-line jsx-a11y/media-has-caption */}
      <audio controls src={mediaStreamUrl(mediaId)} className="w-full" />
      <a
        href={mediaDownloadUrl(mediaId)}
        className="block w-full text-center rounded-md bg-accent text-ink font-medium px-4 py-2 text-sm"
      >
        커버 다운로드
      </a>
    </div>
  );
}
