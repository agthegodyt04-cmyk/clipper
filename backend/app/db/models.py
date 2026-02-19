from __future__ import annotations

from typing import Literal, TypedDict

JobType = Literal[
    "copy_generate",
    "image_generate",
    "image_inpaint",
    "video_storyboard",
    "video_t2v",
]
JobStatus = Literal["queued", "running", "done", "error", "cancelled"]
AssetKind = Literal["copy", "image", "mask", "audio", "video", "subtitle", "meta"]


class ProjectRow(TypedDict):
    id: str
    name: str
    brand_name: str
    product: str
    audience: str
    offer: str
    tone: str
    platform_targets: list[str]
    created_at: str


class JobRow(TypedDict):
    id: str
    project_id: str
    type: str
    status: JobStatus
    progress_pct: int
    stage: str
    params: dict
    result: dict | None
    error_text: str | None
    created_at: str
    updated_at: str


class AssetRow(TypedDict):
    id: str
    project_id: str
    job_id: str | None
    kind: str
    path: str
    meta: dict
    created_at: str

