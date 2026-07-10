from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from tv_guide_data.core.config import load_guide_config
from tv_guide_data.core.models import Programme
from tv_guide_data.core.xmltv import render


def test_xmltv_render() -> None:
    guide = load_guide_config(Path("config/guides/rtve.json"))
    start = datetime(2026, 7, 10, 12, 0, tzinfo=ZoneInfo("Europe/Madrid"))
    data = render(
        guide,
        [
            Programme(
                channel_id="La.1.es",
                start=start,
                stop=start + timedelta(hours=1),
                title="Example",
            )
        ],
    )
    assert b'<channel id="La.1.es">' in data
    assert b'<programme start="20260710120000 +0200"' in data
