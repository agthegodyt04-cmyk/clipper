from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from app.config import Settings

PLATFORM_SIZES: dict[str, tuple[int, int]] = {
    "9:16": (1080, 1920),
    "4:5": (1080, 1350),
    "1:1": (1080, 1080),
}


@dataclass
class CapabilityReport:
    ffmpeg_available: bool
    t2v_enabled: bool
    reason: str


class ModelManager:
    def __init__(self, settings: Settings):
        self.settings = settings

    def platform_size(self, platform: str) -> tuple[int, int]:
        return PLATFORM_SIZES.get(platform, (1080, 1920))

    def ffmpeg_available(self) -> bool:
        if shutil.which("ffmpeg") is not None:
            return True
        try:
            import imageio_ffmpeg  # type: ignore

            exe = imageio_ffmpeg.get_ffmpeg_exe()
            return bool(exe and Path(exe).exists())
        except Exception:  # noqa: BLE001
            return False

    def t2v_capability(self) -> CapabilityReport:
        # User can override for experimentation.
        if os.getenv("CLIPPER_FORCE_T2V", "0") == "1":
            return CapabilityReport(
                ffmpeg_available=self.ffmpeg_available(),
                t2v_enabled=True,
                reason="forced_by_env",
            )

        has_nvidia = shutil.which("nvidia-smi") is not None
        if not has_nvidia:
            cpu_allowed = os.getenv("CLIPPER_ALLOW_CPU_T2V", "0") == "1"
            if cpu_allowed and self.has_local_video_model():
                return CapabilityReport(
                    ffmpeg_available=self.ffmpeg_available(),
                    t2v_enabled=True,
                    reason="cpu_t2v_enabled_with_local_model",
                )
            return CapabilityReport(
                ffmpeg_available=self.ffmpeg_available(),
                t2v_enabled=False,
                reason="nvidia_gpu_not_detected",
            )
        return CapabilityReport(
            ffmpeg_available=self.ffmpeg_available(),
            t2v_enabled=True,
            reason="gpu_detected",
        )

    def has_local_video_model(self) -> bool:
        video_root = self.settings.model_path / "video"
        if not video_root.exists():
            return False
        if (video_root / "model_index.json").exists():
            return True
        for item in video_root.rglob("model_index.json"):
            if item.is_file():
                return True
        return False
