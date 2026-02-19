from __future__ import annotations

import hashlib
import random
import textwrap
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from .model_manager import ModelManager

IMAGE_MODEL_DIRS: dict[str, tuple[str, str]] = {
    "image_fast_sdxl_turbo": ("image", "sdxl-turbo"),
    "image_hq_sdxl_base": ("image", "sdxl-base"),
    "legacy_sd_turbo": ("image", "sd-turbo"),
}

DRAFT_MODEL_ORDER = ["image_fast_sdxl_turbo", "legacy_sd_turbo", "image_hq_sdxl_base"]
HQ_MODEL_ORDER = ["image_hq_sdxl_base", "image_fast_sdxl_turbo", "legacy_sd_turbo"]

RESOLUTION_BUCKETS: dict[str, dict[str, tuple[int, int]]] = {
    "draft": {
        "9:16": (640, 1136),
        "4:5": (768, 960),
        "1:1": (768, 768),
    },
    "hq": {
        "9:16": (768, 1344),
        "4:5": (896, 1152),
        "1:1": (1024, 1024),
    },
}


class ImageGenerator:
    def __init__(self, model_manager: ModelManager):
        self.model_manager = model_manager
        self._pipelines: dict[str, tuple[Any, str]] = {}

    @staticmethod
    def candidate_model_keys(mode: str) -> list[str]:
        return DRAFT_MODEL_ORDER if mode == "draft" else HQ_MODEL_ORDER

    @staticmethod
    def bucket_dimensions(mode: str, platform: str) -> tuple[int, int]:
        bucket = RESOLUTION_BUCKETS["hq" if mode == "hq" else "draft"]
        return bucket.get(platform, bucket["9:16"])

    @staticmethod
    def attempt_plan(width: int, height: int, steps: int) -> list[tuple[int, int, int]]:
        lower_width = ImageGenerator._round_to_64(max(512, int(width * 0.8)))
        lower_height = ImageGenerator._round_to_64(max(512, int(height * 0.8)))
        reduced_steps = max(1, int(steps * 0.7))
        return [
            (width, height, steps),
            (lower_width, lower_height, steps),
            (lower_width, lower_height, reduced_steps),
        ]

    def generate(
        self,
        *,
        prompt: str,
        negative_prompt: str,
        platform: str,
        mode: str,
        output_path: Path,
        seed: int | None = None,
    ) -> dict:
        requested_width, requested_height = self.model_manager.platform_size(platform)
        resolved_seed = seed if seed is not None else self._seed_from_prompt(prompt)
        rng = random.Random(resolved_seed)

        model_key = self._resolve_model_key(mode)
        diffusers_meta, diffusers_error = self._try_generate_with_diffusers(
            model_key=model_key,
            prompt=prompt,
            negative_prompt=negative_prompt,
            output_path=output_path,
            seed=resolved_seed,
            platform=platform,
            mode=mode,
            requested_width=requested_width,
            requested_height=requested_height,
        )
        if diffusers_meta is not None:
            return diffusers_meta

        if self.model_manager.strict_real_image_enabled():
            reason = diffusers_error or "real image pipeline unavailable"
            raise RuntimeError(
                f"Real image generation failed ({reason}). "
                "Placeholder image disabled in strict mode."
            )

        width, height = self.bucket_dimensions(mode, platform)
        image = Image.new("RGB", (width, height), color=self._color(rng))
        draw = ImageDraw.Draw(image)

        # Lightweight deterministic placeholder if no real model is available.
        for _ in range(12):
            x1 = rng.randint(0, max(1, width - 100))
            y1 = rng.randint(0, max(1, height - 100))
            x2 = min(width, x1 + rng.randint(80, width // 2))
            y2 = min(height, y1 + rng.randint(80, height // 2))
            draw.rectangle(
                [x1, y1, x2, y2],
                fill=self._color(rng),
                outline=(255, 255, 255),
                width=2,
            )

        font = ImageFont.load_default()
        header = "HQ AD" if mode == "hq" else "DRAFT AD"
        text = f"{header}\nPrompt: {prompt}\nAvoid: {negative_prompt or 'n/a'}"
        wrapped = "\n".join(
            textwrap.fill(line, width=40) for line in text.splitlines() if line.strip()
        )
        draw.multiline_text(
            (24, 24),
            wrapped,
            fill=(255, 255, 255),
            font=font,
            spacing=6,
            stroke_width=1,
            stroke_fill=(0, 0, 0),
        )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(output_path, format="PNG")
        return {
            "engine": "pillow_fallback",
            "warning": "placeholder_output_only",
            "reason": diffusers_error or "real_model_not_available",
            "platform": platform,
            "mode": mode,
            "seed": resolved_seed,
            "width": width,
            "height": height,
            "requested_width": requested_width,
            "requested_height": requested_height,
            "model_key": model_key or "unavailable",
            "scheduler": self._scheduler_name(model_key),
            "steps": self._steps_for_model(model_key),
            "guidance_scale": self._guidance_scale_for_model(model_key),
            "retry_count": 0,
            "oom_recovered": False,
            "device": "cpu",
        }

    def _try_generate_with_diffusers(
        self,
        *,
        model_key: str | None,
        prompt: str,
        negative_prompt: str,
        output_path: Path,
        seed: int,
        platform: str,
        mode: str,
        requested_width: int,
        requested_height: int,
    ) -> tuple[dict | None, str | None]:
        if model_key is None:
            return None, "model_dir_not_found"
        model_dir = self._model_dir(model_key)
        if model_dir is None:
            return None, "model_dir_not_found"

        pipeline, device, torch, load_error = self._get_diffusers_pipeline(model_key, model_dir)
        if pipeline is None or torch is None:
            return None, load_error or "pipeline_load_failed"

        width, height = self.bucket_dimensions(mode, platform)
        steps = self._steps_for_model(model_key)
        guidance_scale = self._guidance_scale_for_model(model_key)
        attempts = self.attempt_plan(width, height, steps)

        saw_oom = False
        for retry_idx, (gen_width, gen_height, gen_steps) in enumerate(attempts):
            try:
                generator = torch.Generator(device=device).manual_seed(seed)
                result = pipeline(
                    prompt=prompt,
                    negative_prompt=negative_prompt or None,
                    width=gen_width,
                    height=gen_height,
                    num_inference_steps=gen_steps,
                    guidance_scale=guidance_scale,
                    generator=generator,
                )
                image = result.images[0]
                output_path.parent.mkdir(parents=True, exist_ok=True)
                image.save(output_path, format="PNG")
                return {
                    "engine": "diffusers",
                    "platform": platform,
                    "mode": mode,
                    "seed": seed,
                    "width": image.width,
                    "height": image.height,
                    "requested_width": requested_width,
                    "requested_height": requested_height,
                    "model_dir": str(model_dir),
                    "model_key": model_key,
                    "scheduler": self._scheduler_name(model_key),
                    "steps": gen_steps,
                    "guidance_scale": guidance_scale,
                    "retry_count": retry_idx,
                    "oom_recovered": saw_oom and retry_idx > 0,
                    "device": device,
                }, None
            except Exception as exc:  # noqa: BLE001
                message = str(exc)
                if device == "cuda" and self._is_oom_error(message):
                    saw_oom = True
                    if hasattr(torch.cuda, "empty_cache"):
                        torch.cuda.empty_cache()
                    if retry_idx < len(attempts) - 1:
                        continue
                return None, message
        return None, "generation_failed"

    def _resolve_model_key(self, mode: str) -> str | None:
        availability = self.model_manager.image_model_availability()
        for key in self.candidate_model_keys(mode):
            if availability.get(key):
                return key
        return None

    def _model_dir(self, model_key: str) -> Path | None:
        folder = IMAGE_MODEL_DIRS.get(model_key)
        if folder is None:
            return None
        path = self.model_manager.settings.model_path / folder[0] / folder[1]
        if not path.exists():
            return None
        if (path / "model_index.json").exists():
            return path
        for candidate in path.rglob("model_index.json"):
            if candidate.is_file():
                return candidate.parent
        return None

    def _get_diffusers_pipeline(
        self, model_key: str, model_dir: Path
    ) -> tuple[Any | None, str, Any | None, str | None]:
        try:
            import torch  # type: ignore
            from diffusers import AutoPipelineForText2Image  # type: ignore
        except Exception as exc:  # noqa: BLE001
            return None, "cpu", None, f"pipeline_import_failed: {exc}"

        device = "cuda" if torch.cuda.is_available() else "cpu"
        cached = self._pipelines.get(model_key)
        if cached is not None and cached[1] == device:
            return cached[0], device, torch, None

        self._configure_torch(torch=torch, device=device)
        torch_dtype = torch.float16 if device == "cuda" else torch.float32
        try:
            pipe = AutoPipelineForText2Image.from_pretrained(
                str(model_dir),
                torch_dtype=torch_dtype,
                local_files_only=True,
            )
            pipe.to(device)
            self._configure_pipeline_memory(pipe=pipe, device=device)
            self._configure_scheduler(pipe=pipe, model_key=model_key)
            self._pipelines[model_key] = (pipe, device)
            return pipe, device, torch, None
        except Exception as exc:  # noqa: BLE001
            return None, device, torch, f"pipeline_load_failed: {exc}"

    @staticmethod
    def _configure_torch(*, torch: Any, device: str) -> None:
        if device != "cuda":
            return
        try:
            torch.backends.cuda.matmul.allow_tf32 = True
        except Exception:  # noqa: BLE001
            pass
        try:
            torch.set_float32_matmul_precision("high")
        except Exception:  # noqa: BLE001
            pass

    @staticmethod
    def _configure_pipeline_memory(*, pipe: Any, device: str) -> None:
        for fn_name in ("enable_attention_slicing", "enable_vae_slicing", "enable_vae_tiling"):
            fn = getattr(pipe, fn_name, None)
            if callable(fn):
                try:
                    fn()
                except Exception:  # noqa: BLE001
                    pass
        if device == "cuda":
            fn = getattr(pipe, "enable_xformers_memory_efficient_attention", None)
            if callable(fn):
                try:
                    fn()
                except Exception:  # noqa: BLE001
                    pass

    @staticmethod
    def _configure_scheduler(*, pipe: Any, model_key: str) -> None:
        if model_key != "image_hq_sdxl_base":
            return
        try:
            from diffusers import DPMSolverMultistepScheduler  # type: ignore

            pipe.scheduler = DPMSolverMultistepScheduler.from_config(
                pipe.scheduler.config,
                algorithm_type="dpmsolver++",
                use_karras_sigmas=True,
            )
        except Exception:  # noqa: BLE001
            pass

    @staticmethod
    def _scheduler_name(model_key: str | None) -> str:
        if model_key == "image_hq_sdxl_base":
            return "dpmpp_2m_karras"
        return "default"

    @staticmethod
    def _steps_for_model(model_key: str | None) -> int:
        if model_key == "image_hq_sdxl_base":
            return 30
        if model_key in {"image_fast_sdxl_turbo", "legacy_sd_turbo"}:
            return 4
        return 20

    @staticmethod
    def _guidance_scale_for_model(model_key: str | None) -> float:
        if model_key == "image_hq_sdxl_base":
            return 6.5
        if model_key in {"image_fast_sdxl_turbo", "legacy_sd_turbo"}:
            return 0.0
        return 5.5

    @staticmethod
    def _is_oom_error(message: str) -> bool:
        lowered = message.lower()
        return (
            "out of memory" in lowered
            or "cuda out of memory" in lowered
            or "cublas_status_alloc_failed" in lowered
        )

    @staticmethod
    def _seed_from_prompt(prompt: str) -> int:
        digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        return int(digest[:8], 16)

    @staticmethod
    def _color(rng: random.Random) -> tuple[int, int, int]:
        return (rng.randint(20, 220), rng.randint(20, 220), rng.randint(20, 220))

    @staticmethod
    def _round_to_64(value: int) -> int:
        return max(64, (value // 64) * 64)
