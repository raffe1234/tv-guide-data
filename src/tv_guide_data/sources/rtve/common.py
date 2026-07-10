from __future__ import annotations

import html
import re
from datetime import date, datetime, timedelta
from typing import Any
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

from bs4 import Tag

from ...core.models import Channel, Programme

SPANISH_MONTHS = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}


def normalise(value: Any) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"\s+", " ", text).strip().casefold()
    return text.translate(str.maketrans("áéíóúü", "aeiouu"))


def match_channel(name: str, channels: tuple[Channel, ...]) -> Channel | None:
    wanted = normalise(name)
    for channel in channels:
        candidates = (channel.xmltv_id, channel.source_id, *channel.aliases)
        if wanted in {normalise(candidate) for candidate in candidates if candidate}:
            return channel
    return None


def text(node: Tag, selector: str) -> str:
    selected = node.select_one(selector)
    return selected.get_text(" ", strip=True) if isinstance(selected, Tag) else ""


def absolute_attribute(node: Tag, selector: str, attribute: str, base_url: str) -> str:
    selected = node.select_one(selector)
    if not isinstance(selected, Tag):
        return ""
    value = selected.get(attribute)
    return urljoin(base_url, value.strip()) if isinstance(value, str) and value.strip() else ""


def parse_absolute_date(label: str, timezone_name: str) -> datetime | None:
    match = re.search(
        r"(\d{1,2})\s+de\s+"
        r"(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)"
        r"\s+de\s+(\d{4})",
        normalise(label),
    )
    if not match:
        return None
    try:
        return datetime(
            int(match.group(3)),
            SPANISH_MONTHS[match.group(2)],
            int(match.group(1)),
            tzinfo=ZoneInfo(timezone_name),
        )
    except ValueError:
        return None


def parse_relative_date(label: str, now: datetime) -> date | None:
    value = normalise(label)
    if value in {"hoy", "today"}:
        return now.date()
    if value in {"manana", "mañana", "tomorrow"}:
        return (now + timedelta(days=1)).date()
    return None


def parse_time_range(value: str, day: date, timezone_name: str) -> tuple[datetime, datetime] | None:
    match = re.search(r"(\d{1,2}:\d{2})\s*[-–—]\s*(\d{1,2}:\d{2})", value)
    if not match:
        return None
    try:
        start_time = datetime.strptime(match.group(1), "%H:%M").time()
        stop_time = datetime.strptime(match.group(2), "%H:%M").time()
    except ValueError:
        return None
    timezone = ZoneInfo(timezone_name)
    start = datetime.combine(day, start_time, timezone)
    stop = datetime.combine(day, stop_time, timezone)
    if stop <= start:
        stop += timedelta(days=1)
    return start, stop


def programme_from_node(
    node: Tag,
    *,
    channel: Channel,
    day: date,
    timezone_name: str,
    base_url: str,
) -> Programme | None:
    title = text(node, ".maintitle") or str(node.get("data-title") or "").strip()
    time_range = text(node, ".horemi")
    parsed = parse_time_range(time_range, day, timezone_name)
    if not title or not parsed:
        return None
    start, stop = parsed
    description = text(node, ".txtBox > p") or text(node, ".description")
    url = absolute_attribute(node, "a.goto_media[href]", "href", base_url)
    if not url:
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
        url=url,
        icon=icon,
    )
