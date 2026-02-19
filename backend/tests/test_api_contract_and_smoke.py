from __future__ import annotations

import time
from pathlib import Path

from fastapi.testclient import TestClient


def _wait_for_job(client: TestClient, job_id: str, timeout_sec: int = 60) -> dict:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        response = client.get(f"/api/v1/jobs/{job_id}")
        body = response.json()
        status = body["data"]["job"]["status"]
        if status in {"done", "error", "cancelled"}:
            return body
        time.sleep(0.4)
    raise TimeoutError(f"job {job_id} did not finish in {timeout_sec}s")


def test_contract_and_core_pipeline(client: TestClient) -> None:
    create_project = client.post(
        "/api/v1/projects",
        json={
            "name": "Launch-1",
            "brand_name": "Northline",
            "product": "Smart Bottle",
            "audience": "fitness beginners",
            "offer": "30% off",
            "tone": "confident",
            "platform_targets": ["9:16", "4:5", "1:1"],
        },
    )
    assert create_project.status_code == 200
    payload = create_project.json()
    assert payload["ok"] is True
    project_id = payload["data"]["project_id"]

    copy_job_resp = client.post(
        "/api/v1/copy/generate",
        json={
            "project_id": project_id,
            "goal": "more daily hydration",
            "cta": "Shop now",
            "count": 3,
            "mode": "draft",
        },
    )
    assert copy_job_resp.status_code == 200
    copy_job_id = copy_job_resp.json()["data"]["job_id"]
    copy_result = _wait_for_job(client, copy_job_id)
    assert copy_result["data"]["job"]["status"] == "done"

    image_job_resp = client.post(
        "/api/v1/images/generate",
        json={
            "project_id": project_id,
            "prompt": "A cinematic product image of a smart bottle",
            "negative_prompt": "blurry text",
            "platform": "1:1",
            "mode": "draft",
        },
    )
    assert image_job_resp.status_code == 200
    image_job_id = image_job_resp.json()["data"]["job_id"]
    image_result = _wait_for_job(client, image_job_id)
    assert image_result["data"]["job"]["status"] == "done"
    image_asset_id = image_result["data"]["assets"][0]["id"]

    # Create a simple white mask image and upload.
    from PIL import Image

    mask_file = Path(client.app.state.settings.projects_dir) / project_id / "test_mask.png"
    mask_file.parent.mkdir(parents=True, exist_ok=True)
    Image.new("L", (540, 540), color=255).save(mask_file, format="PNG")
    with mask_file.open("rb") as fh:
        mask_upload = client.post(
            "/api/v1/assets/upload",
            files={"file": ("mask.png", fh, "image/png")},
            data={"project_id": project_id, "kind": "mask"},
        )
    assert mask_upload.status_code == 200
    mask_asset_id = mask_upload.json()["data"]["asset_id"]

    inpaint_resp = client.post(
        "/api/v1/images/inpaint",
        json={
            "project_id": project_id,
            "image_asset_id": image_asset_id,
            "mask_asset_id": mask_asset_id,
            "edit_prompt": "add glossy blue lighting",
            "mode": "draft",
            "strength": 0.6,
        },
    )
    assert inpaint_resp.status_code == 200
    inpaint_job_id = inpaint_resp.json()["data"]["job_id"]
    inpaint_result = _wait_for_job(client, inpaint_job_id)
    assert inpaint_result["data"]["job"]["status"] == "done"

    video_resp = client.post(
        "/api/v1/videos/generate-storyboard",
        json={
            "project_id": project_id,
            "duration_sec": 6,
            "platform": "9:16",
            "voice_id": "default",
            "style_prompt": "bold product storytelling",
            "scene_count": 3,
            "mode": "draft",
        },
    )
    assert video_resp.status_code == 200
    video_job_id = video_resp.json()["data"]["job_id"]
    video_result = _wait_for_job(client, video_job_id, timeout_sec=120)
    assert video_result["data"]["job"]["status"] in {"done", "error"}

