from __future__ import annotations

from pathlib import Path

from app.config import Settings
from app.services.copy_gen import CopyGenerator
from app.services.image_gen import ImageGenerator
from app.services.model_manager import PLATFORM_SIZES
from app.services.model_manager import ModelManager
from app.services.prompt_enhancer import PromptEnhancer


def test_platform_dimensions_mapping() -> None:
    assert PLATFORM_SIZES["9:16"] == (1080, 1920)
    assert PLATFORM_SIZES["4:5"] == (1080, 1350)
    assert PLATFORM_SIZES["1:1"] == (1080, 1080)


def test_copy_generator_builds_requested_count() -> None:
    generator = CopyGenerator()
    project = {
        "id": "p1",
        "brand_name": "Nova",
        "product": "Hydration Bottle",
        "audience": "busy runners",
        "offer": "20% launch deal",
        "tone": "bold",
    }
    results = generator.generate(
        project=project,
        goal="better hydration",
        cta="Shop now",
        count=4,
        mode="draft",
    )
    assert len(results) == 4
    assert all("hook" in row and "headline" in row for row in results)


def test_prompt_enhancer_generates_platform_specific_prompt() -> None:
    enhancer = PromptEnhancer()
    project = {
        "id": "p1",
        "brand_name": "Nova",
        "product": "Hydration Bottle",
        "audience": "busy runners",
        "offer": "20% launch deal",
        "tone": "bold",
    }
    result = enhancer.improve(
        project=project,
        prompt="cinematic bottle close-up with water drops",
        platform="9:16",
        mode="hq",
    )
    assert "9:16" in result["prompt"]
    assert "commercial product ad photography" in result["prompt"]
    assert "abstract blobs" in result["negative_prompt"]
    assert len(result["prompt"]) <= 400
    assert len(result["negative_prompt"]) <= 400


def test_image_generator_resolution_buckets() -> None:
    assert ImageGenerator.bucket_dimensions("draft", "9:16") == (640, 1136)
    assert ImageGenerator.bucket_dimensions("draft", "4:5") == (768, 960)
    assert ImageGenerator.bucket_dimensions("hq", "1:1") == (1024, 1024)


def test_image_generator_attempt_plan_retries_lower_cost() -> None:
    attempts = ImageGenerator.attempt_plan(1024, 1024, 30)
    assert attempts[0] == (1024, 1024, 30)
    assert attempts[1][0] < attempts[0][0]
    assert attempts[1][1] < attempts[0][1]
    assert attempts[2][2] < attempts[1][2]


def test_model_manager_defaults_and_strict_env(tmp_path: Path, monkeypatch) -> None:
    settings = Settings(
        model_path=tmp_path / "models",
        data_dir=tmp_path / "data",
        db_path=tmp_path / "data" / "app.db",
        projects_dir=tmp_path / "data" / "projects",
        exports_dir=tmp_path / "data" / "exports",
        max_concurrent_jobs=1,
        default_language="en",
    )
    settings.model_path.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("CLIPPER_STRICT_REAL_IMAGE", "1")
    monkeypatch.setenv("CLIPPER_STRICT_REAL_INPAINT", "1")

    manager = ModelManager(settings)
    assert manager.draft_image_model_default() == "unavailable"
    assert manager.hq_image_model_default() == "unavailable"
    assert manager.strict_real_image_enabled() is True
    assert manager.strict_real_inpaint_enabled() is True
