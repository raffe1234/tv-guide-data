from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from tv_guide_data.core.config import load_guide_config
from tv_guide_data.core.models import GuideConfig, Programme
from tv_guide_data.core.xmltv import validate


def _guide() -> GuideConfig:
    guide = load_guide_config(Path("config/guides/rtve.json"))
    return replace(
        guide,
        minimum_programmes=1,
        required_channels=(),
        coverage_channels=("La.1.es",),
        minimum_future_hours=48,
        maximum_gap_hours=6,
    )


def _programme(start: datetime, stop: datetime, title: str) -> Programme:
    return Programme(
        channel_id="La.1.es",
        start=start,
        stop=stop,
        title=title,
    )


def test_future_coverage_validation_accepts_continuous_schedule() -> None:
    guide = _guide()
    now = datetime(2026, 7, 11, 12, 0, tzinfo=ZoneInfo("Europe/Madrid"))
    programmes = [
        _programme(now - timedelta(hours=1), now + timedelta(hours=24), "Day one"),
        _programme(now + timedelta(hours=24), now + timedelta(hours=50), "Day two"),
    ]

    validate(guide, programmes, now=now)


def test_future_coverage_validation_rejects_short_schedule() -> None:
    guide = _guide()
    now = datetime(2026, 7, 11, 12, 0, tzinfo=ZoneInfo("Europe/Madrid"))
    programmes = [
        _programme(now, now + timedelta(hours=24), "Only one day"),
    ]

    with pytest.raises(RuntimeError, match="24.0 hours of future coverage"):
        validate(guide, programmes, now=now)


def test_future_coverage_validation_rejects_large_gap() -> None:
    guide = _guide()
    now = datetime(2026, 7, 11, 12, 0, tzinfo=ZoneInfo("Europe/Madrid"))
    programmes = [
        _programme(now, now + timedelta(hours=4), "First block"),
        _programme(now + timedelta(hours=12), now + timedelta(hours=60), "Second block"),
    ]

    with pytest.raises(RuntimeError, match="future schedule gap of 8.0 hours"):
        validate(guide, programmes, now=now)
