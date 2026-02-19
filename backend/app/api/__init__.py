from .assets import router as assets_router
from .copy import router as copy_router
from .images import router as images_router
from .jobs import router as jobs_router
from .projects import router as projects_router
from .system import router as system_router
from .videos import router as videos_router

__all__ = [
    "assets_router",
    "copy_router",
    "images_router",
    "jobs_router",
    "projects_router",
    "system_router",
    "videos_router",
]
