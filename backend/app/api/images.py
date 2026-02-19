from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.schemas import ImageGenerateRequest, ImageInpaintRequest, ImagePromptImproveRequest
from app.services.prompt_enhancer import PromptEnhancer

from .common import get_queue, get_repo, ok

router = APIRouter(prefix="/api/v1", tags=["images"])


@router.post("/images/generate")
async def queue_image_generation(request: Request, payload: ImageGenerateRequest) -> dict:
    repo = get_repo(request)
    queue = get_queue(request)

    project = repo.get_project(payload.project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f"project_id '{payload.project_id}' was not found")

    job = repo.create_job(
        project_id=payload.project_id,
        job_type="image_generate",
        params=payload.model_dump(),
    )
    await queue.enqueue(job["id"])
    return ok({"job_id": job["id"], "status": job["status"]})


@router.post("/images/improve-prompt")
async def improve_image_prompt(request: Request, payload: ImagePromptImproveRequest) -> dict:
    repo = get_repo(request)
    project = repo.get_project(payload.project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f"project_id '{payload.project_id}' was not found")

    enhancer = PromptEnhancer()
    result = enhancer.improve(
        project=project,
        prompt=payload.prompt,
        platform=payload.platform,
        mode=payload.mode,
    )
    return ok(result)


@router.post("/images/inpaint")
async def queue_image_inpaint(request: Request, payload: ImageInpaintRequest) -> dict:
    repo = get_repo(request)
    queue = get_queue(request)

    project = repo.get_project(payload.project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f"project_id '{payload.project_id}' was not found")

    image_asset = repo.get_asset(payload.image_asset_id)
    if image_asset is None:
        raise HTTPException(status_code=404, detail=f"image_asset_id '{payload.image_asset_id}' was not found")

    mask_asset = repo.get_asset(payload.mask_asset_id)
    if mask_asset is None:
        raise HTTPException(status_code=404, detail=f"mask_asset_id '{payload.mask_asset_id}' was not found")

    job = repo.create_job(
        project_id=payload.project_id,
        job_type="image_inpaint",
        params=payload.model_dump(),
    )
    await queue.enqueue(job["id"])
    return ok({"job_id": job["id"], "status": job["status"]})
