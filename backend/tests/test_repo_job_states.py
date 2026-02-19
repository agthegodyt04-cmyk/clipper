from __future__ import annotations

from pathlib import Path

from app.db.repo import Repository


def test_job_state_transitions(tmp_path: Path) -> None:
    repo = Repository(tmp_path / "app.db")
    repo.init_db()
    project = repo.create_project(
        name="p",
        brand_name="b",
        product="prod",
        audience="aud",
        offer="off",
        tone="tone",
        platform_targets=["9:16"],
    )
    job = repo.create_job(
        project_id=project["id"],
        job_type="copy_generate",
        params={"project_id": project["id"]},
    )
    assert job["status"] == "queued"
    running = repo.update_job(job["id"], status="running", progress_pct=20, stage="working")
    assert running and running["status"] == "running"
    done = repo.update_job(job["id"], status="done", progress_pct=100, stage="completed")
    assert done and done["status"] == "done"

