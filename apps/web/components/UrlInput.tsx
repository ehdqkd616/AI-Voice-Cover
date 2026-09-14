"use client";

import { FormEvent, useState } from "react";

interface Props {
  onSubmit: (url: string) => void;
  loading?: boolean;
}

export default function UrlInput({ onSubmit, loading }: Props) {
  const [value, setValue] = useState("");

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (value.trim()) onSubmit(value.trim());
  }

  return (
    <form onSubmit={handleSubmit} className="flex gap-2">
      <input
        type="url"
        required
        placeholder="https://www.youtube.com/watch?v=…"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        className="flex-1 rounded-md bg-panel border border-white/10 px-3 py-2 text-sm outline-none focus:border-accent"
      />
      <button
        type="submit"
        disabled={loading}
        className="rounded-md bg-accent text-ink font-medium px-4 py-2 text-sm disabled:opacity-50"
      >
        {loading ? "가져오는 중…" : "가져오기"}
      </button>
    </form>
  );
}
