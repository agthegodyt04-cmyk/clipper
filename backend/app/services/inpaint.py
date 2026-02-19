from __future__ import annotations

import hashlib
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


class InpaintService:
    def __init__(self, model_root: Path):
        self.model_root = model_root
        self._pipeline = None
        self._pipeline_device = "cpu"

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

        strict_real = os.getenv("CLIPPER_STRICT_REAL_INPAINT", "0") == "1"
        if strict_real or self._gpu_available():
            raise RuntimeError(
                f"Real inpaint generation failed ({real_error or 'pipeline unavailable'}). "
                "Placeholder inpaint disabled in strict/GPU mode."
            )

        base = Image.open(image_path).convert("RGB")
        mask = Image.open(mask_path).convert("L").resize(base.size)
        mask = mask.filter(ImageFilter.GaussianBlur(radius=2))

        color = self._prompt_color(edit_prompt)
        tint = Image.new("RGB", base.size, color=color)
        alpha = max(0.05, min(1.0, strength))
        masked_overlay = Image.blend(base, tint, alpha=alpha)
        result = Image.composite(masked_overlay, base, mask)

        # Label changed area for visibility in fallback inpaint mode.
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
        return {
            "engine": "pillow_fallback",
            "warning": "placeholder_output_only",
            "mode": mode,
            "strength": strength,
            "changed_pixels": non_zero,
            "size": {"width": result.width, "height": result.height},
            "reason": real_error or "real_model_not_available",
        }

    @staticmethod
    def _prompt_color(prompt: str) -> tuple[int, int, int]:
        digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        return (int(digest[0:2], 16), int(digest[2:4], 16), int(digest[4:6], 16))

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
        model_dir = self._discover_inpaint_model_dir()
        if model_dir is None:
            return None, "model_dir_not_found"
        pipeline = self._get_pipeline(model_dir)
        if pipeline is None:
            return None, "pipeline_load_failed"

        try:
            import torch  # type: ignore
        except Exception:  # noqa: BLE001
            return None, "torch_not_available"

        base = Image.open(image_path).convert("RGB")
        mask = Image.open(mask_path).convert("L").resize(base.size)
        safe_strength = max(0.05, min(1.0, float(strength)))
        steps = 14 if mode == "draft" else 28

        try:
            generator = torch.Generator(device=self._pipeline_device).manual_seed(
                int(hashlib.sha256(edit_prompt.encode("utf-8")).hexdigest()[:8], 16)
            )
            out = pipeline(
                prompt=edit_prompt,
                image=base,
                mask_image=mask,
                strength=safe_strength,
                num_inference_steps=steps,
                generator=generator,
            )
            image = out.images[0]
            output_path.parent.mkdir(parents=True, exist_ok=True)
            image.save(output_path, format="PNG")
            non_zero = sum(1 for px in mask.getdata() if px > 0)
            return {
                "engine": "diffusers_inpaint",
                "mode": mode,
                "strength": safe_strength,
                "changed_pixels": non_zero,
                "size": {"width": image.width, "height": image.height},
                "device": self._pipeline_device,
                "model_dir": str(model_dir),
            }, None
        except Exception as exc:  # noqa: BLE001
            return None, str(exc)

    def _discover_inpaint_model_dir(self) -> Path | None:
        root = self.model_root / "inpaint"
        if not root.exists():
            return None
        if (root / "model_index.json").exists():
            return root
        for candidate in sorted(root.iterdir()):
            if candidate.is_dir() and (candidate / "model_index.json").exists():
                return candidate
        return None

    def _get_pipeline(self, model_dir: Path):
        if self._pipeline is not None:
            return self._pipeline
        try:
            import torch  # type: ignore
            from diffusers import AutoPipelineForInpainting  # type: ignore
        except Exception:  # noqa: BLE001
            return None
        try:
            self._pipeline_device = "cuda" if torch.cuda.is_available() else "cpu"
            torch_dtype = torch.float16 if self._pipeline_device == "cuda" else torch.float32
            pipe = AutoPipelineForInpainting.from_pretrained(
                str(model_dir),
                torch_dtype=torch_dtype,
                local_files_only=True,
            )
            pipe.to(self._pipeline_device)
            if self._pipeline_device == "cpu":
                try:
                    pipe.enable_attention_slicing()
                except Exception:  # noqa: BLE001
                    pass
            self._pipeline = pipe
            return self._pipeline
        except Exception:  # noqa: BLE001
            return None

    @staticmethod
    def _gpu_available() -> bool:
        try:
            import torch  # type: ignore

            return bool(torch.cuda.is_available())
        except Exception:  # noqa: BLE001
            return False
