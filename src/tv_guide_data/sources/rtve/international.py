from __future__ import annotations

import logging
import re
from datetime import UTC, date, datetime
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup, Tag

from ...core.http import fetch_text
from ...core.models import Channel, GuideConfig, Programme, ProviderConfig
from ...core.source import SourceProvider
from .common import (
    absolute_attribute,
    normalise,
    parse_absolute_date,
    parse_relative_date,
    parse_time_range,
    programme_from_node,
    text,
)

LOGGER = logging.getLogger(__name__)

PROGRAMME_SELECTOR = ", ".join(
    (
        ".mod.video_mod.sched",
        ".video_mod.sched",
        ".sched",
        "article.programme",
        "li.programme",
        "[data-start][data-stop]",
        "[data-start][data-end]",
    )
)

CHANNEL_ATTRIBUTES = (
    "data-channel",
    "data-channel-name",
    "data-canal",
    "data-cadena",
    "data-signal",
    "aria-label",
    "id",
)

DATE_ATTRIBUTES = ("data-date", "data-day", "datetime", "aria-label", "id")


def _target_channels(guide: GuideConfig, channel_ids: tuple[str, ...]) -> tuple[Channel, ...]:
    requested = set(channel_ids)
    channels = tuple(channel for channel in guide.channels if channel.xmltv_id in requested)
    missing = sorted(requested - {channel.xmltv_id for channel in channels})
    if missing:
        raise ValueError(f"Unknown international channel ids: {', '.join(missing)}")
    return channels


def _attribute_values(node: Tag, names: tuple[str, ...]) -> list[str]:
    values: list[str] = []
    for name in names:
        value = node.get(name)
        if isinstance(value, str) and value.strip():
            values.append(value.strip())
        elif isinstance(value, list):
            values.extend(str(item).strip() for item in value if str(item).strip())
    return values


def _match_context_channel(value: str, channels: tuple[Channel, ...]) -> Channel | None:
    wanted = normalise(value)
    if not wanted:
        return None

    matches: list[Channel] = []
    for channel in channels:
        candidates = (channel.source_id, *channel.aliases)
        if any(
            candidate
            and (
                wanted == normalise(candidate)
                or normalise(candidate) in wanted
                or wanted in normalise(candidate)
            )
            for candidate in candidates
        ):
            matches.append(channel)

    unique = {channel.xmltv_id: channel for channel in matches}
    return next(iter(unique.values())) if len(unique) == 1 else None


def _direct_context_values(node: Tag) -> list[str]:
    values = _attribute_values(node, CHANNEL_ATTRIBUTES)

    for child in node.find_all(("h1", "h2", "h3", "h4", "legend"), recursive=False):
        if isinstance(child, Tag):
            value = child.get_text(" ", strip=True)
            if value:
                values.append(value)

    for item in node.find_all(string=True, recursive=False):
        value = str(item).strip()
        if value:
            values.append(value)

    return values


def _channel_from_node(node: Tag, channels: tuple[Channel, ...]) -> Channel | None:
    direct_label = text(
        node,
        ".cademi, .channel-name, .channelName, .canal-name, .canalName",
    )
    channel = _match_context_channel(direct_label, channels)
    if channel is not None:
        return channel

    for value in _attribute_values(node, CHANNEL_ATTRIBUTES):
        channel = _match_context_channel(value, channels)
        if channel is not None:
            return channel

    current = node
    for _ in range(10):
        parent = current.parent
        if not isinstance(parent, Tag) or parent.name in {"body", "html"}:
            break

        for value in _direct_context_values(parent):
            channel = _match_context_channel(value, channels)
            if channel is not None:
                return channel

        current = parent

    return None


def _date_from_label(label: str, local_now: datetime, timezone_name: str) -> date | None:
    relative = parse_relative_date(label, local_now)
    if relative is not None:
        return relative

    absolute = parse_absolute_date(label, timezone_name)
    if absolute is not None:
        return absolute.date()

    normalised = normalise(label)
    iso_match = re.search(r"\b(20\d{2})[-/]([01]?\d)[-/]([0-3]?\d)\b", normalised)
    if iso_match:
        try:
            return date(
                int(iso_match.group(1)),
                int(iso_match.group(2)),
                int(iso_match.group(3)),
            )
        except ValueError:
            return None

    european_match = re.search(r"\b([0-3]?\d)[-/]([01]?\d)[-/](20\d{2})\b", normalised)
    if european_match:
        try:
            return date(
                int(european_match.group(3)),
                int(european_match.group(2)),
                int(european_match.group(1)),
            )
        except ValueError:
            return None

    return None


def _date_from_node(node: Tag, local_now: datetime, timezone_name: str) -> date | None:
    direct_label = text(node, ".datemi, .date, .day, time[datetime]")
    schedule_date = _date_from_label(direct_label, local_now, timezone_name)
    if schedule_date is not None:
        return schedule_date

    for value in _attribute_values(node, DATE_ATTRIBUTES):
        schedule_date = _date_from_label(value, local_now, timezone_name)
        if schedule_date is not None:
            return schedule_date

    current = node
    for _ in range(10):
        parent = current.parent
        if not isinstance(parent, Tag) or parent.name in {"body", "html"}:
            break

        for value in _attribute_values(parent, DATE_ATTRIBUTES):
            schedule_date = _date_from_label(value, local_now, timezone_name)
            if schedule_date is not None:
                return schedule_date

        for heading in parent.find_all(("h1", "h2", "h3", "h4", "time"), recursive=False):
            if not isinstance(heading, Tag):
                continue
            values = [heading.get_text(" ", strip=True)]
            values.extend(_attribute_values(heading, DATE_ATTRIBUTES))
            for value in values:
                schedule_date = _date_from_label(value, local_now, timezone_name)
                if schedule_date is not None:
                    return schedule_date

        current = parent

    return None


def _fallback_programme_from_node(
    node: Tag,
    *,
    channel: Channel,
    day: date,
    timezone_name: str,
    base_url: str,
) -> Programme | None:
    title = text(node, ".maintitle, .title, .program-title, .programme-title, h3, h4")
    time_value = text(node, ".horemi, .time, .schedule-time, .programme-time")

    if not time_value:
        start_value = str(node.get("data-start") or "").strip()
        stop_value = str(node.get("data-stop") or node.get("data-end") or "").strip()
        if start_value and stop_value:
            time_value = f"{start_value} - {stop_value}"

    parsed = parse_time_range(time_value, day, timezone_name)
    if not title or parsed is None:
        return None

    start, stop = parsed
    description = text(node, ".txtBox > p, .description, .summary, p")
    url = absolute_attribute(node, "a[href]", "href", base_url)
    icon = absolute_attribute(node, "img[src]", "src", base_url)
    if not icon:
        icon = absolute_attribute(node, "img[data-src]", "data-src", base_url)

    return Programme(
        channel_id=channel.xmltv_id,
        start=start,
        stop=stop,
        title=title,
        description=description,
        url=urljoin(base_url, url) if url else "",
        icon=urljoin(base_url, icon) if icon else "",
    )


def parse_page(
    page: str,
    guide: GuideConfig,
    channel_ids: tuple[str, ...],
    now: datetime | None = None,
) -> list[Programme]:
    local_now = (now or datetime.now(tz=UTC)).astimezone(ZoneInfo(guide.timezone))
    channels = _target_channels(guide, channel_ids)
    soup = BeautifulSoup(page, "html.parser")

    found: dict[tuple[str, datetime, datetime, str], Programme] = {}
    candidate_count = 0
    skipped_channel = 0
    skipped_date = 0
    skipped_programme = 0
    seen_nodes: set[int] = set()

    for node in soup.select(PROGRAMME_SELECTOR):
        if not isinstance(node, Tag) or id(node) in seen_nodes:
            continue
        seen_nodes.add(id(node))
        candidate_count += 1

        channel = _channel_from_node(node, channels)
        if channel is None:
            skipped_channel += 1
            continue

        schedule_date = _date_from_node(node, local_now, guide.timezone)
        if schedule_date is None:
            skipped_date += 1
            continue

        programme = programme_from_node(
            node,
            channel=channel,
            day=schedule_date,
            timezone_name=guide.timezone,
            base_url=guide.homepage,
        )
        if programme is None:
            programme = _fallback_programme_from_node(
                node,
                channel=channel,
                day=schedule_date,
                timezone_name=guide.timezone,
                base_url=guide.homepage,
            )
        if programme is None:
            skipped_programme += 1
            continue

        key = (programme.channel_id, programme.start, programme.stop, programme.title)
        found[key] = programme

    LOGGER.info(
        "International parser inspected %d candidates: %d programmes, "
        "%d without a target channel, %d without a date, %d without programme data",
        candidate_count,
        len(found),
        skipped_channel,
        skipped_date,
        skipped_programme,
    )

    return sorted(found.values(), key=lambda item: (item.start, item.channel_id, item.title))


def _configured_channel_ids(provider: ProviderConfig) -> tuple[str, ...]:
    value = provider.options.get("channel_ids")
    if (
        not isinstance(value, list)
        or not value
        or not all(isinstance(item, str) and item.strip() for item in value)
    ):
        raise ValueError("InternationalProvider requires a non-empty channel_ids list")
    return tuple(item.strip() for item in value)


class InternationalProvider(SourceProvider):
    def fetch(self, guide: GuideConfig, provider: ProviderConfig) -> list[Programme]:
        url = str(provider.options["url"])
        channel_ids = _configured_channel_ids(provider)
        return parse_page(fetch_text(url), guide, channel_ids)
