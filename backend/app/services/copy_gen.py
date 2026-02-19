from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class CopyVariant:
    hook: str
    headline: str
    primary_text: str
    cta: str

    def to_dict(self) -> dict[str, str]:
        return {
            "hook": self.hook,
            "headline": self.headline,
            "primary_text": self.primary_text,
            "cta": self.cta,
        }


class CopyGenerator:
    def __init__(self, model_root: Path | None = None) -> None:
        self._openers = [
            "Stop scrolling",
            "This is your sign",
            "Built for people who hate wasting time",
            "Small change, big result",
            "If you're serious about results",
        ]
        self.model_root = model_root
        self._llama = None

    def generate(
        self,
        *,
        project: dict[str, Any],
        goal: str,
        cta: str,
        count: int,
        mode: str,
    ) -> list[dict[str, str]]:
        if mode == "hq":
            llama_result = self._try_generate_with_llama(
                project=project,
                goal=goal,
                cta=cta,
                count=count,
            )
            if llama_result:
                return llama_result

        seed = hash(
            (
                project["id"],
                project["brand_name"],
                project["product"],
                goal,
                cta,
                count,
                mode,
            )
        )
        rng = random.Random(seed)
        variants: list[CopyVariant] = []

        for idx in range(count):
            opener = rng.choice(self._openers)
            urgency = "today" if idx % 2 == 0 else "this week"
            tone = project["tone"]
            headline = f"{project['product']} for {project['audience']}"
            if mode == "hq":
                headline = f"{headline} | {project['brand_name']} {goal}"

            primary = (
                f"{opener}: {project['brand_name']} helps {project['audience']} "
                f"unlock {goal} with a {tone} approach. "
                f"Use {project['offer']} and start {urgency}."
            )
            variants.append(
                CopyVariant(
                    hook=f"{opener}. {goal}.",
                    headline=headline,
                    primary_text=primary,
                    cta=cta,
                )
            )

        return [variant.to_dict() for variant in variants]

    def _try_generate_with_llama(
        self, *, project: dict[str, Any], goal: str, cta: str, count: int
    ) -> list[dict[str, str]] | None:
        model_path = self._discover_gguf_model()
        if model_path is None:
            return None
        llama = self._get_llama(model_path)
        if llama is None:
            return None

        prompt = (
            "Create ad copy variants.\n"
            f"Brand: {project['brand_name']}\n"
            f"Product: {project['product']}\n"
            f"Audience: {project['audience']}\n"
            f"Offer: {project['offer']}\n"
            f"Tone: {project['tone']}\n"
            f"Goal: {goal}\n"
            f"CTA: {cta}\n"
            f"Count: {count}\n"
            "Output format:\n"
            "hook | headline | primary_text\n"
            "One variant per line.\n"
        )
        try:
            response = llama.create_completion(
                prompt=prompt,
                max_tokens=700,
                temperature=0.8,
                top_p=0.92,
            )
            text = response["choices"][0]["text"]
        except Exception:  # noqa: BLE001
            return None

        lines = [line.strip() for line in text.splitlines() if "|" in line]
        variants: list[dict[str, str]] = []
        for line in lines[:count]:
            parts = [part.strip() for part in line.split("|", 2)]
            if len(parts) != 3:
                continue
            variants.append(
                {
                    "hook": parts[0],
                    "headline": parts[1],
                    "primary_text": parts[2],
                    "cta": cta,
                }
            )
        return variants or None

    def _discover_gguf_model(self) -> Path | None:
        if self.model_root is None:
            return None
        text_dir = self.model_root / "text"
        if not text_dir.exists():
            return None
        models = sorted(text_dir.glob("*.gguf"))
        return models[0] if models else None

    def _get_llama(self, model_path: Path):
        if self._llama is not None:
            return self._llama
        try:
            from llama_cpp import Llama  # type: ignore
        except Exception:  # noqa: BLE001
            return None
        try:
            self._llama = Llama(
                model_path=str(model_path),
                n_ctx=2048,
                n_threads=4,
                verbose=False,
            )
        except Exception:  # noqa: BLE001
            return None
        return self._llama
