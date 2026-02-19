from __future__ import annotations

import hashlib
import os
import random
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .model_manager import ModelManager


class ImageGenerator:
    def __init__(self, model_manager: ModelManager):
        self.model_manager = model_manager
        self._diffusers_pipeline = None
        self._diffusers_device = "cpu"

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
        width, height = self.model_manager.platform_size(platform)
        if mode == "draft":
            width //= 2
            height //= 2

        resolved_seed = seed if seed is not None else self._seed_from_prompt(prompt)
        requested_width = width
        requested_height = height
        rng = random.Random(resolved_seed)

        diffusers_meta, diffusers_error = self._try_generate_with_diffusers(
            prompt=prompt,
            negative_prompt=negative_prompt,
            output_path=output_path,
            width=width,
            height=height,
            seed=resolved_seed,
            platform=platform,
            mode=mode,
        )
        if diffusers_meta is not None:
            return diffusers_meta

        strict_real = os.getenv("CLIPPER_STRICT_REAL_IMAGE", "0") == "1"
        if strict_real or self._gpu_available():
            reason = diffusers_error or "real image pipeline unavailable"
            raise RuntimeError(
                f"Real image generation failed ({reason}). "
                "Placeholder image disabled in strict/GPU mode."
            )

        image = Image.new("RGB", (width, height), color=self._color(rng))
        draw = ImageDraw.Draw(image)

        # Add geometric blocks so outputs differ per seed while staying lightweight.
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
        margin = 24
        draw.multiline_text(
            (margin, margin),
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
            "width": requested_width,
            "height": requested_height,
            "platform": platform,
            "mode": mode,
            "seed": resolved_seed,
            "reason": diffusers_error or "real_model_not_available",
        }

    @staticmethod
    def _seed_from_prompt(prompt: str) -> int:
        digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        return int(digest[:8], 16)

    @staticmethod
    def _color(rng: random.Random) -> tuple[int, int, int]:
        return (rng.randint(20, 220), rng.randint(20, 220), rng.randint(20, 220))

    def _try_generate_with_diffusers(
        self,
        *,
        prompt: str,
        negative_prompt: str,
        output_path: Path,
        width: int,
        height: int,
        seed: int,
        platform: str,
        mode: str,
    ) -> tuple[dict | None, str | None]:
        model_dir = self._discover_diffusers_model_dir()
        if model_dir is None:
            return None, "model_dir_not_found"
        pipeline = self._get_diffusers_pipeline(model_dir)
        if pipeline is None:
            return None, "pipeline_load_failed"

        try:
            import torch  # type: ignore

            gen_width, gen_height = self._normalize_dimensions(width, height, mode)
            generator = torch.Generator(device=self._diffusers_device).manual_seed(seed)
            steps = self._steps_for_model(model_dir, mode)
            result = pipeline(
                prompt=prompt,
                negative_prompt=negative_prompt or None,
                width=gen_width,
                height=gen_height,
                num_inference_steps=steps,
                generator=generator,
            )
            image = result.images[0]
            output_path.parent.mkdir(parents=True, exist_ok=True)
            image.save(output_path, format="PNG")
            return {
                "engine": "diffusers",
                "width": image.width,
                "height": image.height,
                "requested_width": width,
                "requested_height": height,
                "platform": platform,
                "mode": mode,
                "seed": seed,
                "steps": steps,
                "device": self._diffusers_device,
                "model_dir": str(model_dir),
            }, None
        except Exception as exc:  # noqa: BLE001
            return None, str(exc)

    def _discover_diffusers_model_dir(self) -> Path | None:
        root = self.model_manager.settings.model_path / "image"
        if not root.exists():
            return None
        if (root / "model_index.json").exists():
            return root
        for candidate in sorted(root.iterdir()):
            if candidate.is_dir() and (candidate / "model_index.json").exists():
                return candidate
        return None

    def _get_diffusers_pipeline(self, model_dir: Path):
        if self._diffusers_pipeline is not None:
            return self._diffusers_pipeline
        try:
            import torch  # type: ignore
            from diffusers import AutoPipelineForText2Image  # type: ignore
        except Exception:  # noqa: BLE001
            return None
        try:
            self._diffusers_device = "cuda" if torch.cuda.is_available() else "cpu"
            torch_dtype = torch.float16 if self._diffusers_device == "cuda" else torch.float32
            pipe = AutoPipelineForText2Image.from_pretrained(
                str(model_dir),
                torch_dtype=torch_dtype,
                local_files_only=True,
            )
            pipe.to(self._diffusers_device)
            if self._diffusers_device == "cpu":
                try:
                    pipe.enable_attention_slicing()
                except Exception:  # noqa: BLE001
                    pass
            self._diffusers_pipeline = pipe
            return self._diffusers_pipeline
        except Exception:  # noqa: BLE001
            return None

    @staticmethod
    def _steps_for_model(model_dir: Path, mode: str) -> int:
        lower = str(model_dir).lower()
        if "turbo" in lower:
            return 1 if mode == "draft" else 2
        return 16 if mode == "draft" else 28

    @staticmethod
    def _normalize_dimensions(width: int, height: int, mode: str) -> tuple[int, int]:
        long_target = 768 if mode == "draft" else 1024
        long_side = max(width, height)
        short_side = min(width, height)
        ratio = short_side / max(1, long_side)

        scaled_long = long_target
        scaled_short = max(320, int(scaled_long * ratio))

        if width >= height:
            w, h = scaled_long, scaled_short
        else:
            w, h = scaled_short, scaled_long

        # Diffusion pipelines work best with multiples of 64.
        w = max(320, (w // 64) * 64)
        h = max(320, (h // 64) * 64)
        return w, h

    @staticmethod
    def _gpu_available() -> bool:
        try:
            import torch  # type: ignore

            return bool(torch.cuda.is_available())
        except Exception:  # noqa: BLE001
            return False
