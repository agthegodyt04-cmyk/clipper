from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    os.environ["CLIPPER_DATA_DIR"] = str(tmp_path / "data")
    os.environ["CLIPPER_DB_PATH"] = str(tmp_path / "data" / "app.db")
    os.environ["CLIPPER_PROJECTS_DIR"] = str(tmp_path / "data" / "projects")
    os.environ["CLIPPER_EXPORTS_DIR"] = str(tmp_path / "data" / "exports")
    os.environ["CLIPPER_MODEL_PATH"] = str(tmp_path / "models")
    os.environ["CLIPPER_MAX_CONCURRENT_JOBS"] = "1"

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client

