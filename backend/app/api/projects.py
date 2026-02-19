from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.schemas import ProjectCreateRequest

from .common import get_repo, ok

router = APIRouter(prefix="/api/v1", tags=["projects"])


@router.post("/projects")
async def create_project(request: Request, payload: ProjectCreateRequest) -> dict:
    repo = get_repo(request)
    project = repo.create_project(**payload.model_dump())
    return ok({"project": project, "project_id": project["id"]})


@router.get("/projects")
async def list_projects(request: Request) -> dict:
    repo = get_repo(request)
    projects = repo.list_projects()
    return ok({"projects": projects})


@router.get("/projects/{project_id}")
async def get_project(request: Request, project_id: str) -> dict:
    repo = get_repo(request)
    project = repo.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f"project_id '{project_id}' was not found")
    return ok({"project": project})

