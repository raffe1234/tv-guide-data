from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from tv_guide_data.core.config import load_guide_config
from tv_guide_data.sources.rtve.international import parse_page


def test_international_fixture() -> None:
    guide = load_guide_config(Path("config/guides/rtve.json"))
    page = Path("tests/fixtures/rtve-international.html").read_text(encoding="utf-8")
    now = datetime(2026, 7, 10, 12, 0, tzinfo=ZoneInfo("Europe/Madrid"))

    programmes = parse_page(
        page,
        guide,
        ("TVE.Internacional.es", "Star.es"),
        now=now,
    )

    assert len(programmes) == 4
    assert {programme.channel_id for programme in programmes} == {
        "TVE.Internacional.es",
        "Star.es",
    }

    morning_show = next(programme for programme in programmes if programme.title == "Mañaneros 360")
    assert morning_show.start.isoformat() == "2026-07-10T14:20:00+02:00"
    assert morning_show.stop.isoformat() == "2026-07-10T14:55:00+02:00"
    assert morning_show.url == "https://www.rtve.es/v/17151347"
    assert morning_show.icon == "https://img2.rtve.es/v/17151347?w=100"

    late_show = next(programme for programme in programmes if programme.title == "La Revuelta")
    assert late_show.stop.isoformat() == "2026-07-11T00:25:00+02:00"

    malformed_stop = next(
        programme for programme in programmes if programme.title == "El Caso. Cronica De Sucesos"
    )
    assert malformed_stop.stop.isoformat() == "2026-07-13T06:00:00+02:00"
