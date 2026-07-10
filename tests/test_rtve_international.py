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
    assert programmes[0].start.date().isoformat() == "2026-07-10"
    assert any(programme.stop.date().isoformat() == "2026-07-11" for programme in programmes)
