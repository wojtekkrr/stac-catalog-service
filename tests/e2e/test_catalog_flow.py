from pathlib import Path
from typing import Any

import httpx
import pytest


BASE_URL = "http://localhost:8000"
PROJECT_ROOT = Path(__file__).parents[2]
SAMPLES_DIR = PROJECT_ROOT / "samples"


@pytest.fixture(scope="module")
def ingested_items() -> dict[str, dict[str, Any]]:
    fixtures = {
        "sky": (
            "skyisnolimit",
            "SkyIsNoLimit.json",
            "application/json",
        ),
        "space": (
            "spaceisnolimit",
            "SpaceIsNoLimit.xml",
            "application/xml",
        ),
    }

    results: dict[str, dict[str, Any]] = {}

    with httpx.Client(base_url=BASE_URL, timeout=10) as client:
        for name, (provider, filename, content_type) in fixtures.items():
            response = client.post(
                f"/ingest/{provider}",
                content=(SAMPLES_DIR / filename).read_bytes(),
                headers={"Content-Type": content_type},
            )

            assert response.status_code == 200, response.text
            results[name] = response.json()

    return results


def test_ingests_both_provider_formats(
    ingested_items: dict[str, dict[str, Any]],
) -> None:
    assert ingested_items["sky"]["id"] == ("SKY_SHIELD_20260824_091522_L1C_POL")
    assert ingested_items["space"]["id"] == ("SE02_L2A_20260824T104500_N001")


def test_search_filters_by_cloud_cover(
    ingested_items: dict[str, dict[str, Any]],
) -> None:
    response = httpx.get(
        f"{BASE_URL}/search",
        params={"max_cloud_cover": 5},
        timeout=10,
    )

    assert response.status_code == 200, response.text

    item_ids = {feature["id"] for feature in response.json()["features"]}

    assert ingested_items["space"]["id"] in item_ids
    assert ingested_items["sky"]["id"] not in item_ids


def test_search_filters_by_product_level(
    ingested_items: dict[str, dict[str, Any]],
) -> None:
    response = httpx.get(
        f"{BASE_URL}/search",
        params={"product_level": "L1C"},
        timeout=10,
    )

    assert response.status_code == 200, response.text

    item_ids = {feature["id"] for feature in response.json()["features"]}

    assert ingested_items["sky"]["id"] in item_ids
    assert ingested_items["space"]["id"] not in item_ids
