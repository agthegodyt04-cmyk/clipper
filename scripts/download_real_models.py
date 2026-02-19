from __future__ import annotations

import argparse
from pathlib import Path

from huggingface_hub import HfApi, hf_hub_download, snapshot_download


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def download_text_model(model_root: Path) -> Path:
    text_dir = model_root / "text"
    _ensure_dir(text_dir)

    repo_id = "Qwen/Qwen2.5-1.5B-Instruct-GGUF"
    api = HfApi()
    files = api.list_repo_files(repo_id=repo_id)
    ggufs = [file for file in files if file.lower().endswith(".gguf")]
    preferred = None
    for name in ggufs:
        if "q4_k_m" in name.lower():
            preferred = name
            break
    if preferred is None and ggufs:
        preferred = ggufs[0]
    if preferred is None:
        raise RuntimeError(f"No GGUF files found in {repo_id}.")

    out_path = hf_hub_download(
        repo_id=repo_id,
        filename=preferred,
        local_dir=str(text_dir),
        local_dir_use_symlinks=False,
    )
    return Path(out_path)


def download_image_fast_sdxl_turbo(model_root: Path) -> Path:
    image_dir = model_root / "image" / "sdxl-turbo"
    _ensure_dir(image_dir)
    snapshot_download(
        repo_id="stabilityai/sdxl-turbo",
        local_dir=str(image_dir),
        local_dir_use_symlinks=False,
    )
    return image_dir


def download_image_hq_sdxl_base(model_root: Path) -> Path:
    image_dir = model_root / "image" / "sdxl-base"
    _ensure_dir(image_dir)
    snapshot_download(
        repo_id="stabilityai/stable-diffusion-xl-base-1.0",
        local_dir=str(image_dir),
        local_dir_use_symlinks=False,
    )
    return image_dir


def download_inpaint_hq_sdxl(model_root: Path) -> Path:
    inpaint_dir = model_root / "inpaint" / "sdxl-inpaint"
    _ensure_dir(inpaint_dir)
    snapshot_download(
        repo_id="diffusers/stable-diffusion-xl-1.0-inpainting-0.1",
        local_dir=str(inpaint_dir),
        local_dir_use_symlinks=False,
    )
    return inpaint_dir


def download_legacy_image_model(model_root: Path) -> Path:
    image_dir = model_root / "image" / "sd-turbo"
    _ensure_dir(image_dir)
    snapshot_download(
        repo_id="stabilityai/sd-turbo",
        local_dir=str(image_dir),
        local_dir_use_symlinks=False,
    )
    return image_dir


def download_legacy_inpaint_model(model_root: Path) -> Path:
    inpaint_dir = model_root / "inpaint" / "sd-inpaint"
    _ensure_dir(inpaint_dir)
    snapshot_download(
        repo_id="runwayml/stable-diffusion-inpainting",
        local_dir=str(inpaint_dir),
        local_dir_use_symlinks=False,
    )
    return inpaint_dir


def download_video_model(model_root: Path) -> Path:
    video_dir = model_root / "video" / "zeroscope_v2_576w"
    _ensure_dir(video_dir)
    snapshot_download(
        repo_id="cerspense/zeroscope_v2_576w",
        local_dir=str(video_dir),
        local_dir_use_symlinks=False,
    )
    return video_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Download real local models for Clipper.")
    parser.add_argument("--model-path", default="D:/AIModels")
    all_targets = [
        "text",
        "image_fast_sdxl_turbo",
        "image_hq_sdxl_base",
        "inpaint_hq_sdxl",
        "legacy_sd_turbo",
        "legacy_sd_inpaint",
        "image",
        "inpaint",
        "video",
    ]
    parser.add_argument(
        "--targets",
        nargs="+",
        default=[
            "image_fast_sdxl_turbo",
            "image_hq_sdxl_base",
            "inpaint_hq_sdxl",
        ],
        choices=all_targets,
    )
    args = parser.parse_args()

    model_root = Path(args.model_path)
    _ensure_dir(model_root)

    actions = {
        "text": download_text_model,
        "image_fast_sdxl_turbo": download_image_fast_sdxl_turbo,
        "image_hq_sdxl_base": download_image_hq_sdxl_base,
        "inpaint_hq_sdxl": download_inpaint_hq_sdxl,
        "legacy_sd_turbo": download_legacy_image_model,
        "legacy_sd_inpaint": download_legacy_inpaint_model,
        # Backward-compat aliases.
        "image": download_legacy_image_model,
        "inpaint": download_legacy_inpaint_model,
        "video": download_video_model,
    }

    print(f"Model root: {model_root}")
    print(f"Targets: {', '.join(args.targets)}")

    results: dict[str, str] = {}
    for target in args.targets:
        fn = actions[target]
        print(f"Downloading {target}...")
        try:
            path = fn(model_root)
            results[target] = f"ok -> {path}"
            print(f"{target}: done ({path})")
        except Exception as exc:  # noqa: BLE001
            results[target] = f"failed -> {exc}"
            print(f"{target}: failed ({exc})")

    print("\nSummary:")
    for key in args.targets:
        print(f"- {key}: {results.get(key, 'skipped')}")


if __name__ == "__main__":
    main()
