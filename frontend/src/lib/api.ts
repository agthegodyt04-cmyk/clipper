import type {
  ApiEnvelope,
  Asset,
  CreateProjectPayload,
  GenerateCopyPayload,
  GenerateImagePayload,
  ImproveImagePromptPayload,
  ImproveImagePromptResponse,
  InpaintPayload,
  Job,
  Project,
  StoryboardPayload,
  SystemCapabilities,
  T2VPayload,
} from "../types/api";

const API_BASE_STORAGE_KEY = "clipper_api_base";
const DEFAULT_API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

function normalizeApiBase(input: string): string {
  return input.trim().replace(/\/+$/, "");
}

function queryApiBase(): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  const value = new URLSearchParams(window.location.search).get("apiBase");
  return value ? normalizeApiBase(value) : null;
}

export function getApiBase(): string {
  if (typeof window === "undefined") {
    return normalizeApiBase(DEFAULT_API_BASE);
  }
  const query = queryApiBase();
  if (query) {
    window.localStorage.setItem(API_BASE_STORAGE_KEY, query);
    return query;
  }
  const stored = window.localStorage.getItem(API_BASE_STORAGE_KEY);
  if (stored) {
    return normalizeApiBase(stored);
  }
  return normalizeApiBase(DEFAULT_API_BASE);
}

export function setApiBase(next: string): string {
  const normalized = normalizeApiBase(next);
  if (typeof window !== "undefined") {
    window.localStorage.setItem(API_BASE_STORAGE_KEY, normalized);
  }
  return normalized;
}

export function resetApiBase(): string {
  if (typeof window !== "undefined") {
    window.localStorage.removeItem(API_BASE_STORAGE_KEY);
  }
  return normalizeApiBase(DEFAULT_API_BASE);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${getApiBase()}${path}`, init);
  const body = (await response.json()) as ApiEnvelope<T>;
  if (!response.ok || !body.ok || !body.data) {
    const message = body.error?.message ?? `Request failed: ${response.status}`;
    throw new Error(message);
  }
  return body.data;
}

export async function createProject(payload: CreateProjectPayload): Promise<{ project: Project; project_id: string }> {
  return request("/api/v1/projects", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function listProjects(): Promise<{ projects: Project[] }> {
  return request("/api/v1/projects");
}

export async function getSystemCapabilities(): Promise<SystemCapabilities> {
  return request("/api/v1/system/capabilities");
}

export async function generateCopy(payload: GenerateCopyPayload): Promise<{ job_id: string; status: string }> {
  return request("/api/v1/copy/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function generateImage(payload: GenerateImagePayload): Promise<{ job_id: string; status: string }> {
  return request("/api/v1/images/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function improveImagePrompt(
  payload: ImproveImagePromptPayload,
): Promise<ImproveImagePromptResponse> {
  return request("/api/v1/images/improve-prompt", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function inpaintImage(payload: InpaintPayload): Promise<{ job_id: string; status: string }> {
  return request("/api/v1/images/inpaint", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function generateStoryboard(payload: StoryboardPayload): Promise<{ job_id: string; status: string }> {
  return request("/api/v1/videos/generate-storyboard", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function generateT2V(payload: T2VPayload): Promise<{ job_id: string; status: string }> {
  return request("/api/v1/videos/generate-t2v", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function getJob(jobId: string): Promise<{ job: Job; assets: Asset[] }> {
  return request(`/api/v1/jobs/${jobId}`);
}

export async function listProjectAssets(projectId: string): Promise<{ assets: Asset[] }> {
  return request(`/api/v1/projects/${projectId}/assets`);
}

export async function uploadAsset(
  projectId: string,
  kind: "mask" | "image" | "meta",
  file: File,
): Promise<{ asset: Asset; asset_id: string }> {
  const form = new FormData();
  form.set("project_id", projectId);
  form.set("kind", kind);
  form.set("file", file);
  return request("/api/v1/assets/upload", {
    method: "POST",
    body: form,
  });
}

export async function pollJob(jobId: string, onProgress?: (job: Job) => void): Promise<{ job: Job; assets: Asset[] }> {
  while (true) {
    const result = await getJob(jobId);
    onProgress?.(result.job);
    if (result.job.status === "done" || result.job.status === "error" || result.job.status === "cancelled") {
      return result;
    }
    await new Promise((resolve) => setTimeout(resolve, 1200));
  }
}

export function assetUrl(assetId: string): string {
  return `${getApiBase()}/api/v1/assets/${assetId}`;
}
