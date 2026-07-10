from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from tv_guide_data.core.config import load_guide_config
from tv_guide_data.core.models import Programme
from tv_guide_data.core.xmltv import validate


def test_required_channel_must_have_programmes() -> None:
    guide = load_guide_config(Path("config/guides/rtve.json"))
    guide = replace(
        guide,
        minimum_programmes=1,
        required_channels=("La.1.es", "Star.es"),
        minimum_programmes_per_channel=1,
    )
    start = datetime(2026, 7, 10, 12, 0, tzinfo=ZoneInfo("Europe/Madrid"))
    programmes = [
        Programme(
            channel_id="La.1.es",
            start=start,
            stop=start + timedelta(hours=1),
            title="Example",
        )
    ]

    with pytest.raises(RuntimeError, match=r"Channel Star\.es has 0 programmes"):
        validate(guide, programmes)
