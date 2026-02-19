from __future__ import annotations

from pathlib import Path
from typing import Any

from .model_manager import ModelManager
from .video_storyboard import StoryboardVideoService


class CapabilityError(RuntimeError):
    pass


class TextToVideoService:
    def __init__(
        self,
        model_manager: ModelManager,
        storyboard_service: StoryboardVideoService,
    ):
        self.model_manager = model_manager
        self.storyboard_service = storyboard_service
        self._video_pipeline = None

    def generate_or_fallback(
        self,
        *,
        project: dict[str, Any],
        params: dict[str, Any],
        output_dir: Path,
    ) -> dict[str, Any]:
        capability = self.model_manager.t2v_capability()
        if capability.t2v_enabled:
            real_result = self._try_real_t2v(params=params, output_dir=output_dir)
            if real_result is not None:
                real_result["t2v_mode"] = "local_diffusers"
                real_result["fallback_used"] = False
                real_result["capability_reason"] = capability.reason
                return real_result

        # Capability-gated fallback path required by plan.
        result = self.storyboard_service.generate(
            project=project,
            params={
                "duration_sec": params.get("duration_sec", 8),
                "platform": params.get("platform", "9:16"),
                "scene_count": 4,
                "style_prompt": params.get("prompt", "product ad"),
                "mode": params.get("mode", "draft"),
            },
            output_dir=output_dir,
        )
        result["t2v_mode"] = "disabled_local_fallback"
        result["fallback_used"] = True
        result["capability_reason"] = capability.reason
        return result

    def _try_real_t2v(self, *, params: dict[str, Any], output_dir: Path) -> dict[str, Any] | None:
        model_dir = self._discover_video_model_dir()
        if model_dir is None:
            return None

        pipeline = self._get_video_pipeline(model_dir)
        if pipeline is None:
            return None

        prompt = params.get("prompt", "cinematic product ad")
        duration_sec = int(params.get("duration_sec", 8))
        mode = params.get("mode", "draft")
        steps = 8 if mode == "draft" else 14
        num_frames = max(8, min(24, duration_sec * (2 if mode == "draft" else 3)))

        try:
            result = pipeline(
                prompt=prompt,
                num_inference_steps=steps,
                num_frames=num_frames,
            )
            frames = result.frames[0] if isinstance(result.frames, list) else result.frames
            if not frames:
                return None
        except Exception:  # noqa: BLE001
            return None

        frames_dir = output_dir / "t2v_frames"
        frames_dir.mkdir(parents=True, exist_ok=True)
        frame_paths: list[Path] = []
        for idx, frame in enumerate(frames):
            frame_path = frames_dir / f"frame_{idx:03d}.png"
            frame.save(frame_path, format="PNG")
            frame_paths.append(frame_path)

        video_path = self._render_video_from_frames(
            frame_paths=frame_paths,
            output_path=output_dir / "t2v.mp4",
            duration_sec=duration_sec,
        )
        if video_path is None:
            return None

        return {
            "video_path": str(video_path),
            "frame_paths": [str(path) for path in frame_paths],
            "frame_count": len(frame_paths),
            "model_dir": str(model_dir),
        }

    def _discover_video_model_dir(self) -> Path | None:
        root = self.model_manager.settings.model_path / "video"
        if not root.exists():
            return None
        if (root / "model_index.json").exists():
            return root
        for candidate in sorted(root.iterdir()):
            if candidate.is_dir() and (candidate / "model_index.json").exists():
                return candidate
        return None

    def _get_video_pipeline(self, model_dir: Path):
        if self._video_pipeline is not None:
            return self._video_pipeline
        try:
            from diffusers import DiffusionPipeline  # type: ignore
        except Exception:  # noqa: BLE001
            return None

        try:
            import torch  # type: ignore

            pipe = DiffusionPipeline.from_pretrained(
                str(model_dir),
                torch_dtype=torch.float32,
                local_files_only=True,
            )
            pipe.to("cpu")
            pipe.set_progress_bar_config(disable=True)
            self._video_pipeline = pipe
            return self._video_pipeline
        except Exception:  # noqa: BLE001
            return None

    @staticmethod
    def _render_video_from_frames(
        *,
        frame_paths: list[Path],
        output_path: Path,
        duration_sec: int,
    ) -> Path | None:
        if not frame_paths:
            return None
        try:
            from moviepy import ImageSequenceClip  # type: ignore
        except Exception:  # noqa: BLE001
            return None

        fps = max(4, round(len(frame_paths) / max(1, duration_sec)))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            clip = ImageSequenceClip([str(path) for path in frame_paths], fps=fps)
            clip.write_videofile(
                str(output_path),
                codec="libx264",
                audio=False,
                logger=None,
            )
            clip.close()
            return output_path
        except Exception:  # noqa: BLE001
            try:
                clip.close()
            except Exception:  # noqa: BLE001
                pass
            return None
