from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from tv_guide_data.sources.movistar.argentina import (
    _schedule_url,
    parse_schedule,
)


def test_movistar_argentina_clan_fixture() -> None:
    payload = Path("tests/fixtures/movistar-argentina-clan.json").read_text(encoding="utf-8")

    programmes = parse_schedule(
        payload,
        channel_id="Clan.Internacional.es",
        source_channel_pid="LCH5662",
        timezone_name="Europe/Madrid",
    )

    assert len(programmes) == 2
    assert {programme.channel_id for programme in programmes} == {"Clan.Internacional.es"}

    first = programmes[0]
    assert first.title == "Yoko"
    assert first.start.isoformat() == "2026-07-10T21:13:00+02:00"
    assert first.stop.isoformat() == "2026-07-10T21:25:00+02:00"
    assert first.description.startswith("Un grupo de amigos")
    assert first.icon.startswith("http://media.gvp.telefonica.com/")


def test_schedule_url_uses_unix_seconds() -> None:
    now = datetime(2026, 7, 11, 7, 0, tzinfo=timezone.utc)

    url = _schedule_url(
        "https://example.test/schedules",
        source_channel_pid="LCH5662",
        now=now,
        past_hours=12,
        future_hours=48,
    )

    query = parse_qs(urlparse(url).query)
    assert query["livechannelpids"] == ["LCH5662"]
    assert query["starttime"] == ["1783710000"]
    assert query["endtime"] == ["1783926000"]
    assert len(query["starttime"][0]) == 10
    assert len(query["endtime"][0]) == 10
