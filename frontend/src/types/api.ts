export type RenderMode = "draft" | "hq";
export type PlatformTarget = "9:16" | "4:5" | "1:1";
export type JobStatus = "queued" | "running" | "done" | "error" | "cancelled";

export interface ApiError {
  code: string;
  message: string;
  details?: Record<string, unknown>;
}

export interface ApiEnvelope<T> {
  ok: boolean;
  data: T | null;
  error: ApiError | null;
}

export interface Project {
  id: string;
  name: string;
  brand_name: string;
  product: string;
  audience: string;
  offer: string;
  tone: string;
  platform_targets: PlatformTarget[];
  created_at: string;
}

export interface Job {
  id: string;
  project_id: string;
  type: string;
  status: JobStatus;
  progress_pct: number;
  stage: string;
  params: Record<string, unknown>;
  result?: Record<string, unknown> | null;
  error_text?: string | null;
  created_at: string;
  updated_at: string;
}

export interface Asset {
  id: string;
  project_id: string;
  job_id: string | null;
  kind: string;
  path: string;
  meta: Record<string, unknown>;
  created_at: string;
}

export interface CreateProjectPayload {
  name: string;
  brand_name: string;
  product: string;
  audience: string;
  offer: string;
  tone: string;
  platform_targets: PlatformTarget[];
}

export interface GenerateCopyPayload {
  project_id: string;
  goal: string;
  cta: string;
  count: number;
  mode: RenderMode;
}

export interface GenerateImagePayload {
  project_id: string;
  prompt: string;
  negative_prompt: string;
  platform: PlatformTarget;
  mode: RenderMode;
  seed?: number;
}

export interface InpaintPayload {
  project_id: string;
  image_asset_id: string;
  mask_asset_id: string;
  edit_prompt: string;
  mode: RenderMode;
  strength: number;
}

export interface StoryboardPayload {
  project_id: string;
  duration_sec: number;
  platform: PlatformTarget;
  voice_id: string;
  style_prompt: string;
  scene_count: number;
  mode: RenderMode;
}

export interface T2VPayload {
  project_id: string;
  prompt: string;
  duration_sec: number;
  platform: PlatformTarget;
  mode: RenderMode;
}

