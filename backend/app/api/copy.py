from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.schemas import CopyGenerateRequest

from .common import get_queue, get_repo, ok

router = APIRouter(prefix="/api/v1", tags=["copy"])


@router.post("/copy/generate")
async def queue_copy_generation(request: Request, payload: CopyGenerateRequest) -> dict:
    repo = get_repo(request)
    queue = get_queue(request)

    project = repo.get_project(payload.project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f"project_id '{payload.project_id}' was not found")

    job = repo.create_job(
        project_id=payload.project_id,
        job_type="copy_generate",
        params=payload.model_dump(),
    )
    await queue.enqueue(job["id"])
    return ok({"job_id": job["id"], "status": job["status"]})

