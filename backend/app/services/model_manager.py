from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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

    @staticmethod
    def _env_bool(name: str, default: bool) -> bool:
        raw = os.getenv(name)
        if raw is None:
            return default
        return raw.strip().lower() in {"1", "true", "yes", "on"}

    def ffmpeg_available(self) -> bool:
        if shutil.which("ffmpeg") is not None:
            return True
        try:
            import imageio_ffmpeg  # type: ignore

            exe = imageio_ffmpeg.get_ffmpeg_exe()
            return bool(exe and Path(exe).exists())
        except Exception:  # noqa: BLE001
            return False

    def gpu_info(self) -> dict[str, Any]:
        try:
            import torch  # type: ignore
        except Exception:  # noqa: BLE001
            return {"available": False, "name": None, "vram_gb": None, "cuda": None}

        if not torch.cuda.is_available():
            return {"available": False, "name": None, "vram_gb": None, "cuda": None}
        try:
            idx = torch.cuda.current_device()
            props = torch.cuda.get_device_properties(idx)
            return {
                "available": True,
                "name": str(props.name),
                "vram_gb": round(float(props.total_memory) / (1024**3), 2),
                "cuda": torch.version.cuda,
            }
        except Exception:  # noqa: BLE001
            return {"available": True, "name": "cuda_device", "vram_gb": None, "cuda": None}

    def gpu_available(self) -> bool:
        return bool(self.gpu_info()["available"])

    def strict_real_image_enabled(self) -> bool:
        return self._env_bool("CLIPPER_STRICT_REAL_IMAGE", default=self.gpu_available())

    def strict_real_inpaint_enabled(self) -> bool:
        return self._env_bool("CLIPPER_STRICT_REAL_INPAINT", default=self.gpu_available())

    @staticmethod
    def _has_model_index(path: Path) -> bool:
        if not path.exists():
            return False
        if (path / "model_index.json").exists():
            return True
        for item in path.rglob("model_index.json"):
            if item.is_file():
                return True
        return False

    def image_model_availability(self) -> dict[str, bool]:
        image_root = self.settings.model_path / "image"
        inpaint_root = self.settings.model_path / "inpaint"
        return {
            "image_fast_sdxl_turbo": self._has_model_index(image_root / "sdxl-turbo"),
            "image_hq_sdxl_base": self._has_model_index(image_root / "sdxl-base"),
            "inpaint_hq_sdxl": self._has_model_index(inpaint_root / "sdxl-inpaint"),
            "legacy_sd_turbo": self._has_model_index(image_root / "sd-turbo"),
            "legacy_sd_inpaint": self._has_model_index(inpaint_root / "sd-inpaint"),
        }

    def draft_image_model_default(self) -> str:
        models = self.image_model_availability()
        if models["image_fast_sdxl_turbo"]:
            return "image_fast_sdxl_turbo"
        if models["legacy_sd_turbo"]:
            return "legacy_sd_turbo"
        if models["image_hq_sdxl_base"]:
            return "image_hq_sdxl_base"
        return "unavailable"

    def hq_image_model_default(self) -> str:
        models = self.image_model_availability()
        if models["image_hq_sdxl_base"]:
            return "image_hq_sdxl_base"
        if models["image_fast_sdxl_turbo"]:
            return "image_fast_sdxl_turbo"
        if models["legacy_sd_turbo"]:
            return "legacy_sd_turbo"
        return "unavailable"

    def hq_inpaint_model_default(self) -> str:
        models = self.image_model_availability()
        if models["inpaint_hq_sdxl"]:
            return "inpaint_hq_sdxl"
        if models["legacy_sd_inpaint"]:
            return "legacy_sd_inpaint"
        return "unavailable"

    def system_capabilities(self) -> dict[str, Any]:
        return {
            "gpu": self.gpu_info(),
            "models": self.image_model_availability(),
            "defaults": {
                "draft_model": self.draft_image_model_default(),
                "hq_model": self.hq_image_model_default(),
                "hq_inpaint_model": self.hq_inpaint_model_default(),
            },
            "strict": {
                "real_image": self.strict_real_image_enabled(),
                "real_inpaint": self.strict_real_inpaint_enabled(),
            },
        }

    def t2v_capability(self) -> CapabilityReport:
        # User can override for experimentation.
        if os.getenv("CLIPPER_FORCE_T2V", "0") == "1":
            return CapabilityReport(
                ffmpeg_available=self.ffmpeg_available(),
                t2v_enabled=True,
                reason="forced_by_env",
            )

        has_nvidia = self.gpu_available() or shutil.which("nvidia-smi") is not None
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
