from __future__ import annotations

from app.services.copy_gen import CopyGenerator
from app.services.model_manager import PLATFORM_SIZES


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

