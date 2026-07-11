from pathlib import Path

from tv_guide_data.core.config import load_guide_config
from tv_guide_data.core.models import ProviderConfig
from tv_guide_data.sources.rtve.national import (
    NATIONAL_CHANNEL_IDS,
    _provider_channel_ids,
    _provider_urls,
    parse_page,
)


def test_national_flight_fixture() -> None:
    guide = load_guide_config(Path("config/guides/rtve.json"))
    page = Path("tests/fixtures/rtve-national-flight.html").read_text(encoding="utf-8")

    programmes = parse_page(page, guide)

    assert len(programmes) == 5
    assert {programme.channel_id for programme in programmes} == set(NATIONAL_CHANNEL_IDS)
    assert all(programme.channel_id != "Clan.es" for programme in programmes)

    news = next(
        programme
        for programme in programmes
        if programme.channel_id == "La.1.es" and programme.title == "Noticias 24 H"
    )
    assert news.start.isoformat() == "2026-07-11T06:00:00+02:00"
    assert news.stop.isoformat() == "2026-07-11T08:00:00+02:00"
    assert news.url == "https://www.rtve.es/v/17143793"
    assert news.icon == "https://img.rtve.es/v/17143793?w=400"

    replay = next(programme for programme in programmes if programme.title == "Sports Replay")
    assert replay.stop.isoformat() == "2026-07-12T01:00:00+02:00"


def test_national_legacy_fixture_remains_supported() -> None:
    guide = load_guide_config(Path("config/guides/rtve.json"))
    page = Path("tests/fixtures/rtve-national.html").read_text(encoding="utf-8")

    programmes = parse_page(page, guide)

    assert len(programmes) == 2
    assert programmes[0].channel_id == "La.1.es"
    assert programmes[1].stop.date() > programmes[1].start.date()


def test_national_provider_options() -> None:
    provider = ProviderConfig(
        adapter="tv_guide_data.sources.rtve.national:NationalProvider",
        options={
            "url": "https://example.test/guide/",
            "channel_ids": ["La.1.es", "La.2.es"],
        },
    )

    assert _provider_urls(provider, "https://example.test/") == ("https://example.test/guide/",)
    assert _provider_channel_ids(provider) == ("La.1.es", "La.2.es")
