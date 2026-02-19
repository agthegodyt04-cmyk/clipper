from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.schemas import VideoStoryboardRequest, VideoT2VRequest

from .common import get_queue, get_repo, ok

router = APIRouter(prefix="/api/v1", tags=["videos"])


@router.post("/videos/generate-storyboard")
async def queue_storyboard_video(request: Request, payload: VideoStoryboardRequest) -> dict:
    repo = get_repo(request)
    queue = get_queue(request)

    project = repo.get_project(payload.project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f"project_id '{payload.project_id}' was not found")

    job = repo.create_job(
        project_id=payload.project_id,
        job_type="video_storyboard",
        params=payload.model_dump(),
    )
    await queue.enqueue(job["id"])
    return ok({"job_id": job["id"], "status": job["status"]})


@router.post("/videos/generate-t2v")
async def queue_t2v_video(request: Request, payload: VideoT2VRequest) -> dict:
    repo = get_repo(request)
    queue = get_queue(request)

    project = repo.get_project(payload.project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f"project_id '{payload.project_id}' was not found")

    job = repo.create_job(
        project_id=payload.project_id,
        job_type="video_t2v",
        params=payload.model_dump(),
    )
    await queue.enqueue(job["id"])
    return ok({"job_id": job["id"], "status": job["status"]})

