// Mirrors services/api/app/schemas/*.py. Hand-kept in sync for the MVP —
// a real OpenAPI->TS codegen step is a natural follow-up once the API is
// stable enough to be worth generating from.

export interface User {
  id: string;
  email: string;
  is_approved: boolean;
  is_admin: boolean;
  created_at: string;
}

export interface MeResponse {
  user: User | null;
}

export interface ApiErrorBody {
  error: { code: string; message: string; detail: Record<string, unknown>; retryable: boolean };
}

export interface UploadResponse {
  media_id: string;
  title: string | null;
  duration_sec: number | null;
  content_hash: string;
}

export interface MediaUrlResponse {
  media_id: string;
  url: string;
  expires_in_sec: number;
}

export interface YoutubeInfoResponse {
  video_id: string;
  title: string;
  channel: string;
  duration_sec: number;
  thumbnail: string | null;
  cached: boolean;
}

export interface JobCreatedResponse {
  job_id: string;
  status: string;
  queue_position?: number | null;
  eta_sec?: number | null;
  cached: boolean;
}

export interface JobStatusResponse {
  job_id: string;
  type: string;
  stage: "ingest" | "separate" | "convert" | "mix";
  status: "queued" | "running" | "succeeded" | "failed";
  progress: number;
  output_media: string[] | null;
  error_code: string | null;
  error_message: string | null;
  cache_hit: boolean;
  queued_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface VoiceModel {
  id: string;
  name: string;
  description: string | null;
  thumbnail_url: string | null;
  version: string;
  sample_rate: number;
  has_f0: boolean;
  pairing_confidence: string;
}

export interface VoiceModelAdmin extends VoiceModel {
  weight_filename: string;
  index_filename: string | null;
  is_active: boolean;
}

export type F0Method = "pm" | "rmvpe" | "fcpe";
export type OutputFormat = "mp3-320" | "wav";
export type SeparationQuality = "fast" | "high";
export type SeparationEngine = "demucs" | "mdx_net";

export interface CoverRequest {
  media_id?: string;
  youtube_url?: string;
  voice_model_id: string;
  f0_up_key: number;
  f0_method: F0Method;
  index_rate: number;
  protect: number;
  rms_mix_rate: number;
  output_format: OutputFormat;
  vocal_gain_db: number;
  quality: SeparationQuality;
  separation_engine: SeparationEngine;
  instrumental_pitch: number;
}

export interface LibraryItem {
  job_id: string;
  media_id: string;
  title: string | null;
  artist: string | null;
  voice_model_name: string | null;
  source_type: string | null;
  duration_sec: number | null;
  output_format: string | null;
  created_at: string;
}
