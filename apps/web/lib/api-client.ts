import type {
  ApiErrorBody,
  CoverRequest,
  JobCreatedResponse,
  JobStatusResponse,
  LibraryItem,
  MeResponse,
  UploadResponse,
  User,
  VoiceModel,
  VoiceModelAdmin,
  YoutubeInfoResponse,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8010";

class ApiError extends Error {
  code: string;
  detail: Record<string, unknown>;
  retryable: boolean;

  constructor(body: ApiErrorBody["error"]) {
    super(body.message);
    this.code = body.code;
    this.detail = body.detail;
    this.retryable = body.retryable;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!res.ok) {
    const body = (await res.json()) as ApiErrorBody;
    throw new ApiError(body.error);
  }
  return res.json() as Promise<T>;
}

async function requestForm<T>(path: string, form: FormData, method: string = "POST"): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    body: form,
    credentials: "include",
  });
  if (!res.ok) {
    const body = (await res.json()) as ApiErrorBody;
    throw new ApiError(body.error);
  }
  return res.json();
}

export const api = {
  signup: (email: string, password: string) =>
    request<User>("/api/v1/auth/signup", { method: "POST", body: JSON.stringify({ email, password }) }),

  login: (email: string, password: string) =>
    request<User>("/api/v1/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),

  logout: () => request<{ logged_out: boolean }>("/api/v1/auth/logout", { method: "POST" }),

  me: () => request<MeResponse>("/api/v1/auth/me"),

  adminListUsers: () => request<User[]>("/api/v1/admin/users"),

  adminApprove: (userId: string) =>
    request<User>(`/api/v1/admin/users/${userId}/approve`, { method: "POST" }),

  adminUnapprove: (userId: string) =>
    request<User>(`/api/v1/admin/users/${userId}/unapprove`, { method: "POST" }),

  adminDeleteUser: (userId: string) =>
    request<{ deleted: string }>(`/api/v1/admin/users/${userId}`, { method: "DELETE" }),

  upload: (file: File): Promise<UploadResponse> => {
    const form = new FormData();
    form.append("file", file);
    return requestForm<UploadResponse>("/api/v1/upload", form);
  },

  youtubeInfo: (url: string) =>
    request<YoutubeInfoResponse>("/api/v1/youtube/info", {
      method: "POST",
      body: JSON.stringify({ url }),
    }),

  voiceModels: () => request<VoiceModel[]>("/api/v1/voice-models"),

  adminListVoiceModels: () => request<VoiceModelAdmin[]>("/api/v1/admin/voice-models"),

  adminUploadVoiceModel: (formData: FormData) =>
    requestForm<VoiceModelAdmin>("/api/v1/admin/voice-models", formData),

  adminUpdateVoiceModel: (
    id: string,
    body: { name?: string; description?: string; index_filename?: string; is_active?: boolean }
  ) =>
    request<VoiceModelAdmin>(`/api/v1/admin/voice-models/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),

  adminDeleteVoiceModel: (id: string) =>
    request<{ deleted: string }>(`/api/v1/admin/voice-models/${id}`, { method: "DELETE" }),

  adminUnmatchedIndices: () => request<string[]>("/api/v1/admin/voice-models/unmatched-indices"),

  createCover: (body: CoverRequest) =>
    request<JobCreatedResponse>("/api/v1/cover", { method: "POST", body: JSON.stringify(body) }),

  jobStatus: (jobId: string) => request<JobStatusResponse>(`/api/v1/jobs/${jobId}`),

  jobEventsUrl: (jobId: string) => `${API_BASE}/api/v1/jobs/${jobId}/events`,

  deleteMedia: (mediaId: string) =>
    request<{ deleted: string }>(`/api/v1/media/${mediaId}`, { method: "DELETE" }),

  library: () => request<LibraryItem[]>("/api/v1/library"),

  deleteLibraryItem: (jobId: string) =>
    request<{ deleted: string; cascaded: number }>(`/api/v1/library/${jobId}`, { method: "DELETE" }),
};

// Media bytes proxied through the API (not presigned MinIO URLs) — this
// deployment only exposes the API's own domain publicly (via Caddy), not
// MinIO's, so a presigned S3 URL would point somewhere the browser can't
// reach. <audio src>/<a href> both send the session cookie automatically for
// same-origin requests, so these are plain URL builders, not fetch wrappers.
export const mediaStreamUrl = (mediaId: string) => `${API_BASE}/api/v1/media/${mediaId}/stream`;
export const mediaDownloadUrl = (mediaId: string) => `${API_BASE}/api/v1/media/${mediaId}/file`;

export { ApiError };
