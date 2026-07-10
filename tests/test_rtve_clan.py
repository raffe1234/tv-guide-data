from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from tv_guide_data.core.config import load_guide_config
from tv_guide_data.sources.rtve.clan import parse_page


def test_clan_relative_dates() -> None:
    guide = load_guide_config(Path("config/guides/rtve.json"))
    page = Path("tests/fixtures/rtve-clan.html").read_text(encoding="utf-8")
    now = datetime(2026, 7, 10, 12, 0, tzinfo=ZoneInfo("Europe/Madrid"))
    programmes = parse_page(page, guide, now=now)
    assert len(programmes) == 2
    assert programmes[0].channel_id == "Clan.es"
    assert programmes[0].start.date().isoformat() == "2026-07-10"
    assert programmes[1].start.date().isoformat() == "2026-07-11"
