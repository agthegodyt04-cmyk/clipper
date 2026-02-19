from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFilter, ImageFont

INPAINT_MODEL_DIRS: dict[str, tuple[str, str]] = {
    "inpaint_hq_sdxl": ("inpaint", "sdxl-inpaint"),
    "legacy_sd_inpaint": ("inpaint", "sd-inpaint"),
}

DRAFT_INPAINT_ORDER = ["legacy_sd_inpaint", "inpaint_hq_sdxl"]
HQ_INPAINT_ORDER = ["inpaint_hq_sdxl", "legacy_sd_inpaint"]

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


class InpaintService:
    def __init__(self, model_root: Path):
        self.model_root = model_root
        self._pipelines: dict[str, tuple[Any, str]] = {}

    def apply(
        self,
        *,
        image_path: Path,
        mask_path: Path,
        edit_prompt: str,
        mode: str,
        strength: float,
        output_path: Path,
    ) -> dict:
        real, real_error = self._try_diffusers_inpaint(
            image_path=image_path,
            mask_path=mask_path,
            edit_prompt=edit_prompt,
            mode=mode,
            strength=strength,
            output_path=output_path,
        )
        if real is not None:
            return real

        if self._strict_real_inpaint_enabled():
            raise RuntimeError(
                f"Real inpaint generation failed ({real_error or 'pipeline unavailable'}). "
                "Placeholder inpaint disabled in strict mode."
            )

        base = Image.open(image_path).convert("RGB")
        mask = Image.open(mask_path).convert("L").resize(base.size)
        mask = mask.filter(ImageFilter.GaussianBlur(radius=2))

        color = self._prompt_color(edit_prompt)
        tint = Image.new("RGB", base.size, color=color)
        alpha = max(0.05, min(1.0, strength))
        masked_overlay = Image.blend(base, tint, alpha=alpha)
        result = Image.composite(masked_overlay, base, mask)

        draw = ImageDraw.Draw(result)
        draw.text(
            (20, result.height - 30),
            f"edit: {edit_prompt[:48]}",
            fill=(255, 255, 255),
            font=ImageFont.load_default(),
            stroke_width=1,
            stroke_fill=(0, 0, 0),
        )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        result.save(output_path, format="PNG")

        non_zero = sum(1 for px in mask.getdata() if px > 0)
        model_key = self._resolve_model_key(mode)
        return {
            "engine": "pillow_fallback",
            "warning": "placeholder_output_only",
            "mode": mode,
            "strength": strength,
            "changed_pixels": non_zero,
            "size": {"width": result.width, "height": result.height},
            "reason": real_error or "real_model_not_available",
            "model_key": model_key or "unavailable",
            "scheduler": self._scheduler_name(model_key),
            "steps": self._steps_for_model(model_key),
            "guidance_scale": self._guidance_scale_for_model(model_key),
            "retry_count": 0,
            "oom_recovered": False,
            "device": "cpu",
        }

    def _try_diffusers_inpaint(
        self,
        *,
        image_path: Path,
        mask_path: Path,
        edit_prompt: str,
        mode: str,
        strength: float,
        output_path: Path,
    ) -> tuple[dict | None, str | None]:
        model_key = self._resolve_model_key(mode)
        if model_key is None:
            return None, "model_dir_not_found"
        model_dir = self._model_dir(model_key)
        if model_dir is None:
            return None, "model_dir_not_found"

        pipeline, device, torch, load_error = self._get_pipeline(model_key, model_dir)
        if pipeline is None or torch is None:
            return None, load_error or "pipeline_load_failed"

        base = Image.open(image_path).convert("RGB")
        mask = Image.open(mask_path).convert("L").resize(base.size)
        platform = self._platform_from_size(base.width, base.height)
        width, height = self._bucket_dimensions(mode, platform)
        base = base.resize((width, height), resample=Image.Resampling.LANCZOS)
        mask = mask.resize((width, height), resample=Image.Resampling.LANCZOS)

        safe_strength = max(0.05, min(1.0, float(strength)))
        steps = self._steps_for_model(model_key)
        guidance_scale = self._guidance_scale_for_model(model_key)
        attempts = self._attempt_plan(width=width, height=height, steps=steps)

        saw_oom = False
        for retry_idx, (gen_width, gen_height, gen_steps) in enumerate(attempts):
            try:
                sized_base = base.resize((gen_width, gen_height), resample=Image.Resampling.LANCZOS)
                sized_mask = mask.resize((gen_width, gen_height), resample=Image.Resampling.LANCZOS)
                generator = torch.Generator(device=device).manual_seed(
                    int(hashlib.sha256(edit_prompt.encode("utf-8")).hexdigest()[:8], 16)
                )
                out = pipeline(
                    prompt=edit_prompt,
                    image=sized_base,
                    mask_image=sized_mask,
                    strength=safe_strength,
                    num_inference_steps=gen_steps,
                    guidance_scale=guidance_scale,
                    generator=generator,
                )
                image = out.images[0]
                output_path.parent.mkdir(parents=True, exist_ok=True)
                image.save(output_path, format="PNG")
                non_zero = sum(1 for px in sized_mask.getdata() if px > 0)
                return {
                    "engine": "diffusers_inpaint",
                    "mode": mode,
                    "strength": safe_strength,
                    "changed_pixels": non_zero,
                    "size": {"width": image.width, "height": image.height},
                    "device": device,
                    "model_dir": str(model_dir),
                    "model_key": model_key,
                    "scheduler": self._scheduler_name(model_key),
                    "steps": gen_steps,
                    "guidance_scale": guidance_scale,
                    "retry_count": retry_idx,
                    "oom_recovered": saw_oom and retry_idx > 0,
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
        candidates = HQ_INPAINT_ORDER if mode == "hq" else DRAFT_INPAINT_ORDER
        for model_key in candidates:
            if self._model_dir(model_key) is not None:
                return model_key
        return None

    def _model_dir(self, model_key: str) -> Path | None:
        folder = INPAINT_MODEL_DIRS.get(model_key)
        if folder is None:
            return None
        path = self.model_root / folder[0] / folder[1]
        if not path.exists():
            return None
        if (path / "model_index.json").exists():
            return path
        for candidate in path.rglob("model_index.json"):
            if candidate.is_file():
                return candidate.parent
        return None

    def _get_pipeline(
        self, model_key: str, model_dir: Path
    ) -> tuple[Any | None, str, Any | None, str | None]:
        cached = self._pipelines.get(model_key)
        try:
            import torch  # type: ignore
            from diffusers import AutoPipelineForInpainting  # type: ignore
        except Exception as exc:  # noqa: BLE001
            return None, "cpu", None, f"pipeline_import_failed: {exc}"

        device = "cuda" if torch.cuda.is_available() else "cpu"
        if cached is not None and cached[1] == device:
            return cached[0], device, torch, None

        self._configure_torch(torch=torch, device=device)
        torch_dtype = torch.float16 if device == "cuda" else torch.float32
        try:
            pipe = AutoPipelineForInpainting.from_pretrained(
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
        if model_key != "inpaint_hq_sdxl":
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
    def _platform_from_size(width: int, height: int) -> str:
        if width <= 0 or height <= 0:
            return "9:16"
        ratio = width / height
        targets = {
            "9:16": 9 / 16,
            "4:5": 4 / 5,
            "1:1": 1.0,
        }
        return min(targets.keys(), key=lambda key: abs(targets[key] - ratio))

    @staticmethod
    def _bucket_dimensions(mode: str, platform: str) -> tuple[int, int]:
        bucket = RESOLUTION_BUCKETS["hq" if mode == "hq" else "draft"]
        return bucket.get(platform, bucket["9:16"])

    @staticmethod
    def _attempt_plan(width: int, height: int, steps: int) -> list[tuple[int, int, int]]:
        lower_width = InpaintService._round_to_64(max(512, int(width * 0.8)))
        lower_height = InpaintService._round_to_64(max(512, int(height * 0.8)))
        reduced_steps = max(1, int(steps * 0.7))
        return [
            (width, height, steps),
            (lower_width, lower_height, steps),
            (lower_width, lower_height, reduced_steps),
        ]

    @staticmethod
    def _steps_for_model(model_key: str | None) -> int:
        if model_key == "inpaint_hq_sdxl":
            return 30
        if model_key == "legacy_sd_inpaint":
            return 20
        return 20

    @staticmethod
    def _guidance_scale_for_model(model_key: str | None) -> float:
        if model_key == "inpaint_hq_sdxl":
            return 6.5
        return 5.0

    @staticmethod
    def _scheduler_name(model_key: str | None) -> str:
        if model_key == "inpaint_hq_sdxl":
            return "dpmpp_2m_karras"
        return "default"

    @staticmethod
    def _is_oom_error(message: str) -> bool:
        lowered = message.lower()
        return (
            "out of memory" in lowered
            or "cuda out of memory" in lowered
            or "cublas_status_alloc_failed" in lowered
        )

    def _strict_real_inpaint_enabled(self) -> bool:
        raw = os.getenv("CLIPPER_STRICT_REAL_INPAINT")
        if raw is not None:
            return raw.strip().lower() in {"1", "true", "yes", "on"}
        return self._gpu_available()

    @staticmethod
    def _gpu_available() -> bool:
        try:
            import torch  # type: ignore

            return bool(torch.cuda.is_available())
        except Exception:  # noqa: BLE001
            return False

    @staticmethod
    def _prompt_color(prompt: str) -> tuple[int, int, int]:
        digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        return (int(digest[0:2], 16), int(digest[2:4], 16), int(digest[4:6], 16))

    @staticmethod
    def _round_to_64(value: int) -> int:
        return max(64, (value // 64) * 64)
