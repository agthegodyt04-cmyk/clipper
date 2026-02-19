from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Request

from app.db.repo import Repository
from app.services.job_queue import JobQueue


def ok(data: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"ok": True, "data": data or {}, "error": None}


def err(*, code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"ok": False, "data": None, "error": {"code": code, "message": message, "details": details}}


def raise_not_found(entity: str, entity_id: str) -> None:
    raise HTTPException(
        status_code=404,
        detail=err(code=f"{entity}_not_found", message=f"{entity} '{entity_id}' was not found."),
    )


def get_repo(request: Request) -> Repository:
    return request.app.state.repo


def get_queue(request: Request) -> JobQueue:
    return request.app.state.job_queue

