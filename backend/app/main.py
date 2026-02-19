from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import (
    assets_router,
    copy_router,
    images_router,
    jobs_router,
    projects_router,
    videos_router,
)
from app.config import ensure_dirs, get_settings
from app.db.repo import Repository
from app.services.job_queue import JobQueue
from app.services.model_manager import ModelManager
from app.services.orchestrator import GenerationOrchestrator


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    ensure_dirs(settings)

    repo = Repository(settings.db_path)
    repo.init_db()

    model_manager = ModelManager(settings)
    orchestrator = GenerationOrchestrator(repo, settings, model_manager)

    queue = JobQueue(repo, max_workers=settings.max_concurrent_jobs)
    for job_type, handler in orchestrator.handlers().items():
        queue.register_handler(job_type, handler)
    await queue.start()

    app.state.settings = settings
    app.state.repo = repo
    app.state.model_manager = model_manager
    app.state.job_queue = queue

    try:
        yield
    finally:
        await queue.stop()


app = FastAPI(title="Clipper Local AI Ad Generator", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects_router)
app.include_router(copy_router)
app.include_router(images_router)
app.include_router(videos_router)
app.include_router(jobs_router)
app.include_router(assets_router)


@app.get("/health")
async def health() -> dict:
    return {"ok": True, "data": {"status": "up"}, "error": None}


@app.exception_handler(HTTPException)
async def http_exception_handler(_request, exc: HTTPException):
    detail = exc.detail
    if isinstance(detail, dict) and {"ok", "data", "error"}.issubset(detail.keys()):
        payload = detail
    else:
        payload = {
            "ok": False,
            "data": None,
            "error": {
                "code": "http_error",
                "message": str(detail),
                "details": {"status_code": exc.status_code},
            },
        }
    return JSONResponse(status_code=exc.status_code, content=payload)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "ok": False,
            "data": None,
            "error": {
                "code": "validation_error",
                "message": "Request validation failed.",
                "details": {"errors": exc.errors()},
            },
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(_request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "ok": False,
            "data": None,
            "error": {
                "code": "internal_error",
                "message": str(exc),
                "details": None,
            },
        },
    )
