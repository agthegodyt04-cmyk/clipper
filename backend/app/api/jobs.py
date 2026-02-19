from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from .common import get_repo, ok

router = APIRouter(prefix="/api/v1", tags=["jobs"])


@router.get("/jobs/{job_id}")
async def get_job(request: Request, job_id: str) -> dict:
    repo = get_repo(request)
    job = repo.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"job_id '{job_id}' was not found")

    assets = repo.list_assets(job_id=job_id)
    return ok({"job": job, "assets": assets})


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(request: Request, job_id: str) -> dict:
    repo = get_repo(request)
    job = repo.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"job_id '{job_id}' was not found")
    if job["status"] in {"done", "error", "cancelled"}:
        return ok({"job": job, "cancelled": False})
    updated = repo.cancel_job(job_id)
    return ok({"job": updated, "cancelled": True})

