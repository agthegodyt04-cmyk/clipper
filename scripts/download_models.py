from __future__ import annotations

import argparse
from pathlib import Path


STARTER_NOTES = [
    "Starter profile (~8-12GB target):",
    "1) Small GGUF instruct model for copy generation (optional fallback exists).",
    "2) Lightweight text-to-image model checkpoint.",
    "3) Inpaint checkpoint.",
]

FULL_NOTES = [
    "Full profile (~20-35GB target):",
    "1) Larger GGUF instruct model.",
    "2) Higher quality image/inpaint checkpoints.",
    "3) Optional local text-to-video model prep artifacts.",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare local model folders for Clipper.")
    parser.add_argument("--profile", choices=["starter", "full"], default="starter")
    parser.add_argument("--model-path", default="D:/AIModels")
    args = parser.parse_args()

    model_root = Path(args.model_path)
    (model_root / ".cache").mkdir(parents=True, exist_ok=True)
    (model_root / "text").mkdir(parents=True, exist_ok=True)
    (model_root / "image").mkdir(parents=True, exist_ok=True)
    (model_root / "inpaint").mkdir(parents=True, exist_ok=True)
    (model_root / "video").mkdir(parents=True, exist_ok=True)

    notes = STARTER_NOTES if args.profile == "starter" else FULL_NOTES
    readme = model_root / "MODEL_DOWNLOAD_INSTRUCTIONS.txt"
    readme.write_text(
        "\n".join(
            [
                f"Profile: {args.profile}",
                "",
                *notes,
                "",
                "This script creates folder structure only.",
                "Place downloaded model files into the matching folders.",
                "Set CLIPPER_MODEL_PATH if using a custom path.",
            ]
        ),
        encoding="utf-8",
    )
    print(f"Prepared model directory at: {model_root}")
    print(f"Wrote instructions: {readme}")


if __name__ == "__main__":
    main()

