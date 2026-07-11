from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from typing import cast
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from ...core.http import fetch_text
from ...core.models import GuideConfig, Programme, ProviderConfig
from ...core.source import SourceProvider

LOGGER = logging.getLogger(__name__)

DEFAULT_PAST_HOURS = 12
DEFAULT_FUTURE_HOURS = 48
DEFAULT_LIMIT = 1000


def _mapping(value: object) -> Mapping[str, object] | None:
    if not isinstance(value, dict):
        return None
    return cast(Mapping[str, object], value)


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _number(value: object) -> float | None:
    if isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        result = float(value)
    elif isinstance(value, str):
        try:
            result = float(value)
        except ValueError:
            return None
    else:
        return None

    if result > 10_000_000_000:
        result /= 1000

    return result


def _positive_int_option(
    provider: ProviderConfig,
    key: str,
    default: int,
) -> int:
    value = provider.options.get(key, default)
    if isinstance(value, bool):
        raise ValueError(f"{key} must be a positive integer")

    if isinstance(value, int):
        result = value
    elif isinstance(value, str):
        try:
            result = int(value)
        except ValueError as error:
            raise ValueError(f"{key} must be a positive integer") from error
    else:
        raise ValueError(f"{key} must be a positive integer")

    if result < 1:
        raise ValueError(f"{key} must be a positive integer")

    return result


def _required_option(provider: ProviderConfig, key: str) -> str:
    value = provider.options.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"ClanInternationalProvider requires {key}")
    return value.strip()


def _target_channel(guide: GuideConfig, channel_id: str) -> str:
    if channel_id not in {channel.xmltv_id for channel in guide.channels}:
        raise ValueError(f"Unknown Clan International channel id: {channel_id}")
    return channel_id


def _schedule_url(
    base_url: str,
    *,
    source_channel_pid: str,
    now: datetime,
    past_hours: int,
    future_hours: int,
) -> str:
    if now.tzinfo is None:
        raise ValueError("Schedule reference time must be timezone-aware")

    reference = now.astimezone(timezone.utc)
    start_time = int((reference - timedelta(hours=past_hours)).timestamp())
    end_time = int((reference + timedelta(hours=future_hours)).timestamp())

    parameters = {
        "ca_deviceTypes": "null|401",
        "fields": (
            "Pid,Title,Description,ChannelName,ChannelNumber,CallLetter,"
            "Start,End,EpgNetworkDvr,LiveChannelPid,LiveProgramPid,"
            "EpgSerieId,SeriesPid,SeriesId,SeasonPid,SeasonNumber,"
            "images.videoFrame,images.banner,LiveToVod,AgeRatingPid"
        ),
        "includeRelations": "Genre",
        "orderBy": "START_TIME:a",
        "filteravailability": "false",
        "includeAttributes": ("ca_cpvrDisable,ca_descriptors,ca_blackout_target,ca_blackout_areas"),
        "livechannelpids": source_channel_pid,
        "offset": "0",
        "limit": str(DEFAULT_LIMIT),
        "starttime": str(start_time),
        "endtime": str(end_time),
    }

    separator = "&" if "?" in base_url else "?"
    return f"{base_url}{separator}{urlencode(parameters)}"


def _icon(item: Mapping[str, object]) -> str:
    images = _mapping(item.get("Images"))
    if images is None:
        return ""

    for group_name in ("VideoFrame", "Banner"):
        group = images.get(group_name)
        if not isinstance(group, list):
            continue

        for raw_image in cast(list[object], group):
            image = _mapping(raw_image)
            if image is None:
                continue

            url = _text(image.get("Url"))
            if url:
                return url

    return ""


def parse_schedule(
    payload: str,
    *,
    channel_id: str,
    source_channel_pid: str,
    timezone_name: str,
) -> list[Programme]:
    raw_payload: object = json.loads(payload)
    document = _mapping(raw_payload)
    if document is None:
        raise ValueError("Movistar schedule response must be a JSON object")

    raw_content = document.get("Content")
    if not isinstance(raw_content, list):
        raise ValueError("Movistar schedule response does not contain Content")

    timezone_info = ZoneInfo(timezone_name)
    found: dict[tuple[datetime, datetime, str], Programme] = {}
    candidate_count = 0
    ignored_channel_count = 0
    invalid_count = 0

    for raw_item in cast(list[object], raw_content):
        item = _mapping(raw_item)
        if item is None:
            invalid_count += 1
            continue

        candidate_count += 1
        if _text(item.get("LiveChannelPid")) != source_channel_pid:
            ignored_channel_count += 1
            continue

        title = _text(item.get("Title"))
        description = _text(item.get("Description"))
        start_timestamp = _number(item.get("Start"))
        stop_timestamp = _number(item.get("End"))

        if not title or start_timestamp is None or stop_timestamp is None:
            invalid_count += 1
            continue
        if stop_timestamp <= start_timestamp:
            invalid_count += 1
            continue

        try:
            start = datetime.fromtimestamp(start_timestamp, timezone_info)
            stop = datetime.fromtimestamp(stop_timestamp, timezone_info)
        except (OverflowError, OSError, ValueError):
            invalid_count += 1
            continue

        programme = Programme(
            channel_id=channel_id,
            start=start,
            stop=stop,
            title=title,
            description=description,
            icon=_icon(item),
        )
        found[(start, stop, title)] = programme

    LOGGER.info(
        "Movistar Argentina parser inspected %d candidates: %d programmes, "
        "%d other-channel entries, %d invalid",
        candidate_count,
        len(found),
        ignored_channel_count,
        invalid_count,
    )

    return sorted(found.values(), key=lambda programme: programme.start)


class ClanInternationalProvider(SourceProvider):
    def fetch(self, guide: GuideConfig, provider: ProviderConfig) -> list[Programme]:
        base_url = _required_option(provider, "url")
        channel_id = _target_channel(
            guide,
            _required_option(provider, "channel_id"),
        )
        source_channel_pid = _required_option(provider, "source_channel_pid")
        past_hours = _positive_int_option(
            provider,
            "past_hours",
            DEFAULT_PAST_HOURS,
        )
        future_hours = _positive_int_option(
            provider,
            "future_hours",
            DEFAULT_FUTURE_HOURS,
        )

        url = _schedule_url(
            base_url,
            source_channel_pid=source_channel_pid,
            now=datetime.now(timezone.utc),
            past_hours=past_hours,
            future_hours=future_hours,
        )
        return parse_schedule(
            fetch_text(url),
            channel_id=channel_id,
            source_channel_pid=source_channel_pid,
            timezone_name=guide.timezone,
        )
