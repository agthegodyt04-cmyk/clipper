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

export interface SystemCapabilities {
  gpu: {
    available: boolean;
    name: string | null;
    vram_gb: number | null;
    cuda: string | null;
  };
  models: {
    image_fast_sdxl_turbo: boolean;
    image_hq_sdxl_base: boolean;
    inpaint_hq_sdxl: boolean;
    legacy_sd_turbo: boolean;
    legacy_sd_inpaint: boolean;
  };
  defaults: {
    draft_model: string;
    hq_model: string;
    hq_inpaint_model: string;
  };
  strict: {
    real_image: boolean;
    real_inpaint: boolean;
  };
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

export interface ImproveImagePromptPayload {
  project_id: string;
  prompt: string;
  platform: PlatformTarget;
  mode: RenderMode;
}

export interface ImproveImagePromptResponse {
  prompt: string;
  negative_prompt: string;
  notes: string[];
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
