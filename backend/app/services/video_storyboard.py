from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from .image_gen import ImageGenerator
from .model_manager import ModelManager


class StoryboardVideoService:
    def __init__(self, image_generator: ImageGenerator, model_manager: ModelManager):
        self.image_generator = image_generator
        self.model_manager = model_manager

    def generate(
        self,
        *,
        project: dict[str, Any],
        params: dict[str, Any],
        output_dir: Path,
    ) -> dict[str, Any]:
        output_dir.mkdir(parents=True, exist_ok=True)
        scene_dir = output_dir / "scenes"
        scene_dir.mkdir(parents=True, exist_ok=True)

        scene_count = int(params.get("scene_count", 4))
        duration_sec = int(params.get("duration_sec", 15))
        style_prompt = params.get("style_prompt", "clean product ad")
        platform = params.get("platform", "9:16")
        mode = params.get("mode", "draft")

        prompts = self._scene_prompts(project=project, style_prompt=style_prompt, count=scene_count)
        scene_paths: list[Path] = []
        for idx, prompt in enumerate(prompts):
            scene_path = scene_dir / f"scene_{idx + 1:02d}.png"
            self.image_generator.generate(
                prompt=prompt,
                negative_prompt="",
                platform=platform,
                mode=mode,
                output_path=scene_path,
                seed=idx + 11,
            )
            scene_paths.append(scene_path)

        narration = self._build_script(project=project, scene_count=scene_count)
        narration_path = output_dir / "narration.txt"
        narration_path.write_text(narration, encoding="utf-8")

        subtitle_path = output_dir / "subtitles.srt"
        subtitle_path.write_text(
            self._build_srt(narration=narration, duration_sec=duration_sec),
            encoding="utf-8",
        )

        audio_path = self._try_generate_tts_wav(narration, output_dir / "voiceover.wav")
        video_path = self._try_render_video(
            scene_paths=scene_paths,
            output_path=output_dir / "storyboard.mp4",
            duration_sec=duration_sec,
            audio_path=audio_path,
        )

        metadata = {
            "scene_count": scene_count,
            "duration_sec": duration_sec,
            "platform": platform,
            "mode": mode,
            "ffmpeg_available": self.model_manager.ffmpeg_available(),
            "video_rendered": video_path is not None,
        }
        manifest_path = output_dir / "storyboard_manifest.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "prompts": prompts,
                    "narration_path": str(narration_path),
                    "subtitle_path": str(subtitle_path),
                    "audio_path": str(audio_path) if audio_path else None,
                    "video_path": str(video_path) if video_path else None,
                    "metadata": metadata,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        return {
            "scene_paths": [str(path) for path in scene_paths],
            "narration_path": str(narration_path),
            "subtitle_path": str(subtitle_path),
            "audio_path": str(audio_path) if audio_path else None,
            "video_path": str(video_path) if video_path else None,
            "manifest_path": str(manifest_path),
            "metadata": metadata,
        }

    def _scene_prompts(self, *, project: dict[str, Any], style_prompt: str, count: int) -> list[str]:
        return [
            (
                f"{style_prompt}. Scene {idx + 1}: {project['product']} for {project['audience']}. "
                f"Tone: {project['tone']}. Offer: {project['offer']}."
            )
            for idx in range(count)
        ]

    def _build_script(self, *, project: dict[str, Any], scene_count: int) -> str:
        lines = [
            f"{project['brand_name']} presents {project['product']}.",
            f"Built for {project['audience']}.",
            f"Get started with {project['offer']}.",
            "Tap now and launch your next result today.",
        ]
        if scene_count > len(lines):
            lines.extend(["Act now. Limited momentum window."] * (scene_count - len(lines)))
        return " ".join(lines[:scene_count])

    def _build_srt(self, *, narration: str, duration_sec: int) -> str:
        chunks = [chunk.strip() for chunk in narration.split(".") if chunk.strip()]
        if not chunks:
            chunks = ["Your ad is ready."]
        per_chunk = max(1, math.floor(duration_sec / len(chunks)))

        lines: list[str] = []
        for idx, chunk in enumerate(chunks):
            start = idx * per_chunk
            end = duration_sec if idx == len(chunks) - 1 else (idx + 1) * per_chunk
            lines.extend(
                [
                    str(idx + 1),
                    f"{self._fmt_srt_time(start)} --> {self._fmt_srt_time(end)}",
                    chunk + ".",
                    "",
                ]
            )
        return "\n".join(lines)

    @staticmethod
    def _fmt_srt_time(total_sec: int) -> str:
        hh = total_sec // 3600
        mm = (total_sec % 3600) // 60
        ss = total_sec % 60
        return f"{hh:02d}:{mm:02d}:{ss:02d},000"

    @staticmethod
    def _try_generate_tts_wav(script: str, out_path: Path) -> Path | None:
        try:
            import pyttsx3  # type: ignore
        except Exception:  # noqa: BLE001
            return None

        try:
            engine = pyttsx3.init()
            out_path.parent.mkdir(parents=True, exist_ok=True)
            engine.save_to_file(script, str(out_path))
            engine.runAndWait()
            if out_path.exists() and out_path.stat().st_size > 0:
                return out_path
        except Exception:  # noqa: BLE001
            return None
        return None

    @staticmethod
    def _try_render_video(
        *,
        scene_paths: list[Path],
        output_path: Path,
        duration_sec: int,
        audio_path: Path | None,
    ) -> Path | None:
        try:
            from moviepy import AudioFileClip, ImageClip, concatenate_videoclips  # type: ignore
        except Exception:  # noqa: BLE001
            return None

        if not scene_paths:
            return None

        clip_duration = max(1, duration_sec / len(scene_paths))
        clips = [ImageClip(str(path)).with_duration(clip_duration) for path in scene_paths]
        final_clip = concatenate_videoclips(clips, method="compose")

        if audio_path and audio_path.exists():
            try:
                audio_clip = AudioFileClip(str(audio_path))
                final_clip = final_clip.with_audio(audio_clip)
            except Exception:  # noqa: BLE001
                pass

        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            final_clip.write_videofile(
                str(output_path),
                fps=24,
                codec="libx264",
                audio_codec="aac",
                logger=None,
            )
            final_clip.close()
            return output_path
        except Exception:  # noqa: BLE001
            try:
                final_clip.close()
            except Exception:  # noqa: BLE001
                pass
            return None

