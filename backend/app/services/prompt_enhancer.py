from __future__ import annotations

import re
from typing import Any


class PromptEnhancer:
    _NEGATIVE_COMMON = [
        "blurry",
        "low quality",
        "lowres",
        "noisy",
        "grainy",
        "pixelated",
        "abstract blobs",
        "distorted product",
        "deformed shape",
        "warped label",
        "duplicate object",
        "cropped out of frame",
        "text artifacts",
        "watermark",
        "logo",
        "jpeg artifacts",
    ]

    def improve(
        self,
        *,
        project: dict[str, Any],
        prompt: str,
        platform: str,
        mode: str,
    ) -> dict[str, Any]:
        cleaned_prompt = self._clean(prompt)
        if not cleaned_prompt:
            cleaned_prompt = (
                f"{project['product']} hero shot for {project['brand_name']} ad campaign"
            )

        composition = self._composition(platform)
        quality = (
            "ultra clean details, photorealistic, crisp focus, studio lighting"
            if mode == "hq"
            else "clean details, clear focus, product photography lighting"
        )
        audience_hint = project.get("audience", "").strip()
        offer_hint = project.get("offer", "").strip()
        tone_hint = project.get("tone", "").strip()

        prompt_parts = [
            cleaned_prompt,
            f"featuring {project['brand_name']} {project['product']}",
            "commercial product ad photography",
            composition,
            "single primary product centered",
            "minimal uncluttered background",
            quality,
        ]
        if tone_hint:
            prompt_parts.append(f"{tone_hint} ad tone")
        if audience_hint:
            prompt_parts.append(f"for {audience_hint}")
        if offer_hint:
            prompt_parts.append(f"subtle campaign message: {offer_hint}")

        improved_prompt = ", ".join(prompt_parts)
        improved_prompt = self._limit(improved_prompt, 400)

        negative_prompt = ", ".join(self._NEGATIVE_COMMON)
        if mode == "hq":
            negative_prompt += ", oversaturated colors, harsh posterization, banding"
        negative_prompt = self._limit(negative_prompt, 400)

        return {
            "prompt": improved_prompt,
            "negative_prompt": negative_prompt,
            "notes": [
                "Adds product-photo language that diffusion models follow more reliably.",
                "Adds platform-specific framing and stronger quality constraints.",
                "Strengthens negative prompt to avoid blob/noise artifacts.",
            ],
        }

    @staticmethod
    def _composition(platform: str) -> str:
        if platform == "9:16":
            return "vertical 9:16 frame, centered subject, negative space near top for headline"
        if platform == "4:5":
            return "portrait 4:5 frame, centered subject, breathing room around product"
        return "square 1:1 frame, balanced centered product composition"

    @staticmethod
    def _clean(text: str) -> str:
        compact = re.sub(r"\s+", " ", text).strip()
        return compact

    @staticmethod
    def _limit(text: str, max_len: int) -> str:
        compact = re.sub(r"\s+", " ", text).strip()
        if len(compact) <= max_len:
            return compact
        clipped = compact[:max_len].rstrip(",;: ")
        if " " not in clipped:
            return clipped
        return clipped.rsplit(" ", 1)[0]
