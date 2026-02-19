from __future__ import annotations

import hashlib
import random
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .model_manager import ModelManager


class ImageGenerator:
    def __init__(self, model_manager: ModelManager):
        self.model_manager = model_manager
        self._diffusers_pipeline = None

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
        rng = random.Random(resolved_seed)

        if mode == "hq":
            diffusers_meta = self._try_generate_with_diffusers(
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
            "width": width,
            "height": height,
            "platform": platform,
            "mode": mode,
            "seed": resolved_seed,
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
    ) -> dict | None:
        model_dir = self._discover_diffusers_model_dir()
        if model_dir is None:
            return None
        pipeline = self._get_diffusers_pipeline(model_dir)
        if pipeline is None:
            return None

        try:
            import torch  # type: ignore

            generator = torch.Generator(device="cpu").manual_seed(seed)
            result = pipeline(
                prompt=prompt,
                negative_prompt=negative_prompt or None,
                width=width,
                height=height,
                num_inference_steps=14 if mode == "draft" else 28,
                generator=generator,
            )
            image = result.images[0]
            output_path.parent.mkdir(parents=True, exist_ok=True)
            image.save(output_path, format="PNG")
            return {
                "engine": "diffusers",
                "width": width,
                "height": height,
                "platform": platform,
                "mode": mode,
                "seed": seed,
                "model_dir": str(model_dir),
            }
        except Exception:  # noqa: BLE001
            return None

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
            from diffusers import AutoPipelineForText2Image  # type: ignore
        except Exception:  # noqa: BLE001
            return None
        try:
            pipe = AutoPipelineForText2Image.from_pretrained(
                str(model_dir),
                local_files_only=True,
            )
            pipe.to("cpu")
            self._diffusers_pipeline = pipe
            return self._diffusers_pipeline
        except Exception:  # noqa: BLE001
            return None
