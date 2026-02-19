from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    model_path: Path
    data_dir: Path
    db_path: Path
    projects_dir: Path
    exports_dir: Path
    max_concurrent_jobs: int
    default_language: str


def get_settings() -> Settings:
    repo_root = Path(__file__).resolve().parents[2]
    data_dir = Path(os.getenv("CLIPPER_DATA_DIR", str(repo_root / "data")))
    model_path = Path(os.getenv("CLIPPER_MODEL_PATH", "D:/AIModels"))
    max_jobs = _env_int("CLIPPER_MAX_CONCURRENT_JOBS", 1)

    settings = Settings(
        model_path=model_path,
        data_dir=data_dir,
        db_path=Path(os.getenv("CLIPPER_DB_PATH", str(data_dir / "app.db"))),
        projects_dir=Path(
            os.getenv("CLIPPER_PROJECTS_DIR", str(data_dir / "projects"))
        ),
        exports_dir=Path(os.getenv("CLIPPER_EXPORTS_DIR", str(data_dir / "exports"))),
        max_concurrent_jobs=max(1, max_jobs),
        default_language=os.getenv("CLIPPER_DEFAULT_LANGUAGE", "en"),
    )
    return settings


def ensure_dirs(settings: Settings) -> None:
    settings.model_path.mkdir(parents=True, exist_ok=True)
    (settings.model_path / ".cache").mkdir(parents=True, exist_ok=True)
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.projects_dir.mkdir(parents=True, exist_ok=True)
    settings.exports_dir.mkdir(parents=True, exist_ok=True)
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)

