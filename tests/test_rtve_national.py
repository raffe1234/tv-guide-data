from pathlib import Path

from tv_guide_data.core.config import load_guide_config
from tv_guide_data.core.models import ProviderConfig
from tv_guide_data.sources.rtve.national import _provider_urls, parse_page, parse_pages


def test_national_fixture() -> None:
    guide = load_guide_config(Path("config/guides/rtve.json"))
    page = Path("tests/fixtures/rtve-national.html").read_text(encoding="utf-8")

    programmes = parse_page(page, guide)

    assert len(programmes) == 2
    assert programmes[0].channel_id == "La.1.es"
    assert programmes[1].stop.date() > programmes[1].start.date()


def test_multiple_national_pages_are_combined_and_deduplicated() -> None:
    guide = load_guide_config(Path("config/guides/rtve.json"))
    today = Path("tests/fixtures/rtve-national.html").read_text(encoding="utf-8")
    tomorrow = Path("tests/fixtures/rtve-national-tomorrow.html").read_text(encoding="utf-8")

    programmes = parse_pages((today, today, tomorrow), guide)

    assert len(programmes) == 4
    assert {programme.start.date().isoformat() for programme in programmes} == {
        "2026-07-10",
        "2026-07-12",
    }


def test_national_provider_accepts_multiple_urls() -> None:
    provider = ProviderConfig(
        adapter="tv_guide_data.sources.rtve.national:NationalProvider",
        options={
            "urls": [
                "https://example.test/today/",
                "https://example.test/tomorrow/",
            ]
        },
    )

    assert _provider_urls(provider, "https://example.test/") == (
        "https://example.test/today/",
        "https://example.test/tomorrow/",
    )
