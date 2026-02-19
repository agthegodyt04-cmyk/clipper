from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from app.config import Settings
from app.db.repo import Repository

from .copy_gen import CopyGenerator
from .image_gen import ImageGenerator
from .inpaint import InpaintService
from .model_manager import ModelManager
from .video_storyboard import StoryboardVideoService
from .video_t2v import TextToVideoService

ProgressFn = Callable[[str, int], Awaitable[None]]


class GenerationOrchestrator:
    def __init__(self, repo: Repository, settings: Settings, model_manager: ModelManager):
        self.repo = repo
        self.settings = settings
        self.model_manager = model_manager
        self.copy_gen = CopyGenerator(settings.model_path)
        self.image_gen = ImageGenerator(model_manager)
        self.inpaint = InpaintService(settings.model_path)
        self.storyboard = StoryboardVideoService(self.image_gen, self.model_manager)
        self.t2v = TextToVideoService(self.model_manager, self.storyboard)

    def handlers(self) -> dict[str, Callable[[dict[str, Any], ProgressFn], Awaitable[dict]]]:
        return {
            "copy_generate": self.handle_copy_generate,
            "image_generate": self.handle_image_generate,
            "image_inpaint": self.handle_image_inpaint,
            "video_storyboard": self.handle_video_storyboard,
            "video_t2v": self.handle_video_t2v,
        }

    async def handle_copy_generate(self, job: dict[str, Any], progress: ProgressFn) -> dict:
        params = job["params"]
        project = self._require_project(params["project_id"])
        await progress("copy_generating", 20)

        variants = await asyncio.to_thread(
            self.copy_gen.generate,
            project=project,
            goal=params["goal"],
            cta=params["cta"],
            count=params.get("count", 3),
            mode=params.get("mode", "draft"),
        )
        await progress("copy_saving", 80)

        out_dir = self._job_dir(project_id=project["id"], job_id=job["id"])
        out_dir.mkdir(parents=True, exist_ok=True)
        copy_path = out_dir / "copy_variants.json"
        copy_path.write_text(json.dumps(variants, indent=2), encoding="utf-8")
        asset = self.repo.create_asset(
            project_id=project["id"],
            job_id=job["id"],
            kind="copy",
            path=str(copy_path),
            meta={"count": len(variants), "mode": params.get("mode", "draft")},
        )
        return {"asset_ids": [asset["id"]], "variants": variants}

    async def handle_image_generate(self, job: dict[str, Any], progress: ProgressFn) -> dict:
        params = job["params"]
        project = self._require_project(params["project_id"])
        await progress("image_generating", 30)

        out_dir = self._job_dir(project_id=project["id"], job_id=job["id"])
        image_path = out_dir / "image.png"
        metadata = await asyncio.to_thread(
            self.image_gen.generate,
            prompt=params["prompt"],
            negative_prompt=params.get("negative_prompt", ""),
            platform=params.get("platform", "9:16"),
            mode=params.get("mode", "draft"),
            output_path=image_path,
            seed=params.get("seed"),
        )
        await progress("image_saving", 85)
        asset = self.repo.create_asset(
            project_id=project["id"],
            job_id=job["id"],
            kind="image",
            path=str(image_path),
            meta=metadata,
        )
        return {"asset_ids": [asset["id"]], "image_meta": metadata}

    async def handle_image_inpaint(self, job: dict[str, Any], progress: ProgressFn) -> dict:
        params = job["params"]
        project = self._require_project(params["project_id"])
        image_asset = self.repo.get_asset(params["image_asset_id"])
        mask_asset = self.repo.get_asset(params["mask_asset_id"])
        if image_asset is None:
            raise ValueError("image_asset_id was not found.")
        if mask_asset is None:
            raise ValueError("mask_asset_id was not found.")

        image_path = Path(image_asset["path"])
        mask_path = Path(mask_asset["path"])
        if not image_path.exists():
            raise FileNotFoundError(f"Base image missing: {image_path}")
        if not mask_path.exists():
            raise FileNotFoundError(f"Mask image missing: {mask_path}")

        await progress("inpaint_editing", 35)
        out_dir = self._job_dir(project_id=project["id"], job_id=job["id"])
        out_path = out_dir / "inpaint.png"
        metadata = await asyncio.to_thread(
            self.inpaint.apply,
            image_path=image_path,
            mask_path=mask_path,
            edit_prompt=params["edit_prompt"],
            mode=params.get("mode", "draft"),
            strength=params.get("strength", 0.6),
            output_path=out_path,
        )
        await progress("inpaint_saving", 85)
        asset = self.repo.create_asset(
            project_id=project["id"],
            job_id=job["id"],
            kind="image",
            path=str(out_path),
            meta={
                **metadata,
                "source_image_asset_id": image_asset["id"],
                "source_mask_asset_id": mask_asset["id"],
            },
        )
        return {"asset_ids": [asset["id"]], "inpaint_meta": metadata}

    async def handle_video_storyboard(self, job: dict[str, Any], progress: ProgressFn) -> dict:
        params = job["params"]
        project = self._require_project(params["project_id"])
        out_dir = self._job_dir(project_id=project["id"], job_id=job["id"])

        await progress("storyboard_planning", 15)
        result = await asyncio.to_thread(
            self.storyboard.generate,
            project=project,
            params=params,
            output_dir=out_dir,
        )
        await progress("storyboard_assets", 80)

        asset_ids: list[str] = []
        for scene_path in result["scene_paths"]:
            asset = self.repo.create_asset(
                project_id=project["id"],
                job_id=job["id"],
                kind="image",
                path=scene_path,
                meta={"type": "story_scene"},
            )
            asset_ids.append(asset["id"])

        subtitle = self.repo.create_asset(
            project_id=project["id"],
            job_id=job["id"],
            kind="subtitle",
            path=result["subtitle_path"],
            meta={"format": "srt"},
        )
        asset_ids.append(subtitle["id"])

        manifest = self.repo.create_asset(
            project_id=project["id"],
            job_id=job["id"],
            kind="meta",
            path=result["manifest_path"],
            meta={"format": "json"},
        )
        asset_ids.append(manifest["id"])

        if result["audio_path"]:
            audio = self.repo.create_asset(
                project_id=project["id"],
                job_id=job["id"],
                kind="audio",
                path=result["audio_path"],
                meta={"format": "wav"},
            )
            asset_ids.append(audio["id"])

        if result["video_path"]:
            video = self.repo.create_asset(
                project_id=project["id"],
                job_id=job["id"],
                kind="video",
                path=result["video_path"],
                meta=result.get("metadata", {}),
            )
            asset_ids.append(video["id"])

        return {
            "asset_ids": asset_ids,
            "video_path": result["video_path"],
            "metadata": result.get("metadata", {}),
        }

    async def handle_video_t2v(self, job: dict[str, Any], progress: ProgressFn) -> dict:
        params = job["params"]
        project = self._require_project(params["project_id"])
        out_dir = self._job_dir(project_id=project["id"], job_id=job["id"])

        await progress("t2v_capability_check", 10)
        result = await asyncio.to_thread(
            self.t2v.generate_or_fallback,
            project=project,
            params=params,
            output_dir=out_dir,
        )
        await progress("t2v_assets", 80)

        asset_ids: list[str] = []
        for scene_path in result.get("scene_paths", []):
            scene = self.repo.create_asset(
                project_id=project["id"],
                job_id=job["id"],
                kind="image",
                path=scene_path,
                meta={"type": "t2v_fallback_scene"},
            )
            asset_ids.append(scene["id"])

        if result.get("video_path"):
            video = self.repo.create_asset(
                project_id=project["id"],
                job_id=job["id"],
                kind="video",
                path=result["video_path"],
                meta={
                    "t2v_mode": result.get("t2v_mode"),
                    "fallback_used": result.get("fallback_used", True),
                    "capability_reason": result.get("capability_reason"),
                },
            )
            asset_ids.append(video["id"])

        manifest = result.get("manifest_path")
        if manifest:
            meta_asset = self.repo.create_asset(
                project_id=project["id"],
                job_id=job["id"],
                kind="meta",
                path=manifest,
                meta={
                    "t2v_mode": result.get("t2v_mode"),
                    "fallback_used": result.get("fallback_used", True),
                    "capability_reason": result.get("capability_reason"),
                },
            )
            asset_ids.append(meta_asset["id"])

        return {
            "asset_ids": asset_ids,
            "fallback_used": result.get("fallback_used", True),
            "capability_reason": result.get("capability_reason"),
            "video_path": result.get("video_path"),
        }

    def _require_project(self, project_id: str) -> dict[str, Any]:
        project = self.repo.get_project(project_id)
        if project is None:
            raise ValueError(f"project_id '{project_id}' was not found.")
        return project

    def _job_dir(self, *, project_id: str, job_id: str) -> Path:
        return self.settings.projects_dir / project_id / "jobs" / job_id
