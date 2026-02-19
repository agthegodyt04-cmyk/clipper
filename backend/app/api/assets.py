from __future__ import annotations

import shutil
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse

from app.config import Settings

from .common import get_repo, ok

router = APIRouter(prefix="/api/v1", tags=["assets"])


@router.post("/assets/upload")
async def upload_asset(
    request: Request,
    project_id: str = Form(...),
    kind: Literal["mask", "image", "meta"] = Form(...),
    file: UploadFile = File(...),
) -> dict:
    repo = get_repo(request)
    settings: Settings = request.app.state.settings
    project = repo.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f"project_id '{project_id}' was not found")

    project_dir = settings.projects_dir / project_id / "uploads"
    project_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(file.filename or "upload.bin").name
    out_path = project_dir / safe_name
    with out_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    asset = repo.create_asset(
        project_id=project_id,
        job_id=None,
        kind=kind,
        path=str(out_path),
        meta={"uploaded_name": safe_name, "content_type": file.content_type},
    )
    return ok({"asset": asset, "asset_id": asset["id"]})


@router.get("/assets/{asset_id}")
async def get_asset_file(request: Request, asset_id: str):
    repo = get_repo(request)
    asset = repo.get_asset(asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail=f"asset_id '{asset_id}' was not found")
    file_path = Path(asset["path"])
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"asset file missing at '{file_path}'")
    return FileResponse(file_path)


@router.get("/projects/{project_id}/assets")
async def list_project_assets(request: Request, project_id: str) -> dict:
    repo = get_repo(request)
    project = repo.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f"project_id '{project_id}' was not found")
    assets = repo.list_assets(project_id=project_id)
    return ok({"assets": assets})

