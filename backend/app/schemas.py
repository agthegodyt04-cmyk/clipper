from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

RenderMode = Literal["draft", "hq"]
PlatformTarget = Literal["9:16", "4:5", "1:1"]
JobStatus = Literal["queued", "running", "done", "error", "cancelled"]


class ApiError(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None = None


class ApiEnvelope(BaseModel):
    ok: bool
    data: dict[str, Any] | None = None
    error: ApiError | None = None


class ProjectCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    brand_name: str = Field(min_length=1, max_length=120)
    product: str = Field(min_length=1, max_length=200)
    audience: str = Field(min_length=1, max_length=300)
    offer: str = Field(min_length=1, max_length=300)
    tone: str = Field(min_length=1, max_length=80)
    platform_targets: list[PlatformTarget] = Field(default_factory=lambda: ["9:16"])


class CopyGenerateRequest(BaseModel):
    project_id: str
    goal: str = Field(min_length=2, max_length=160)
    cta: str = Field(min_length=1, max_length=80)
    count: int = Field(default=3, ge=1, le=10)
    mode: RenderMode = "draft"


class ImageGenerateRequest(BaseModel):
    project_id: str
    prompt: str = Field(min_length=2, max_length=400)
    negative_prompt: str = Field(default="", max_length=400)
    platform: PlatformTarget = "9:16"
    mode: RenderMode = "draft"
    seed: int | None = None


class ImageInpaintRequest(BaseModel):
    project_id: str
    image_asset_id: str
    mask_asset_id: str
    edit_prompt: str = Field(min_length=2, max_length=400)
    mode: RenderMode = "draft"
    strength: float = Field(default=0.6, ge=0.05, le=1.0)


class VideoStoryboardRequest(BaseModel):
    project_id: str
    duration_sec: int = Field(default=15, ge=5, le=60)
    platform: PlatformTarget = "9:16"
    voice_id: str = "default"
    style_prompt: str = Field(default="clean product ad", max_length=300)
    scene_count: int = Field(default=4, ge=2, le=10)
    mode: RenderMode = "draft"


class VideoT2VRequest(BaseModel):
    project_id: str
    prompt: str = Field(min_length=2, max_length=400)
    duration_sec: int = Field(default=8, ge=4, le=20)
    platform: PlatformTarget = "9:16"
    mode: RenderMode = "draft"


class AssetUploadResponse(BaseModel):
    asset_id: str
    path: str

