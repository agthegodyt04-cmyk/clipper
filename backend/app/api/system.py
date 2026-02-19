from __future__ import annotations

from fastapi import APIRouter, Request

from .common import ok

router = APIRouter(prefix="/api/v1", tags=["system"])


@router.get("/system/capabilities")
async def get_system_capabilities(request: Request) -> dict:
    model_manager = request.app.state.model_manager
    return ok(model_manager.system_capabilities())
