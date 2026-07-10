from __future__ import annotations

import html
import re
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup, Tag

from ..config import SourceConfig
from ..models import Channel, Programme

USER_AGENT = "tv-guide-data/0.1 (+https://github.com/raffe1234/tv-guide-data)"

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


def _normalise(value: Any) -> str:
    """Normalise text for reliable channel-name comparisons."""
    text = html.unescape(str(value or ""))
    text = re.sub(r"\s+", " ", text).strip().casefold()

    replacements = {
        "á": "a",
        "é": "e",
        "í": "i",
        "ó": "o",
        "ú": "u",
        "ü": "u",
    }

    for source, replacement in replacements.items():
        text = text.replace(source, replacement)

    return text


def _fetch(url: str, timeout: int = 45) -> str:
    """Download the RTVE programme-guide page."""
    response = requests.get(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,"
                "image/avif,image/webp,*/*;q=0.8"
            ),
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.5",
        },
        timeout=timeout,
    )
    response.raise_for_status()

    if response.apparent_encoding:
        response.encoding = response.apparent_encoding

    return response.text


def _parse_schedule_date(
    label: str,
    timezone_name: str,
) -> datetime | None:
    """
    Parse dates such as:

    'Programación del 10 de julio de 2026'
    'Viernes 10 de julio de 2026'
    """
    normalised = _normalise(label)

    match = re.search(
        r"(\d{1,2})\s+de\s+"
        r"(enero|febrero|marzo|abril|mayo|junio|julio|agosto|"
        r"septiembre|octubre|noviembre|diciembre)"
        r"\s+de\s+(\d{4})",
        normalised,
    )

    if match is None:
        return None

    day = int(match.group(1))
    month = SPANISH_MONTHS[match.group(2)]
    year = int(match.group(3))

    try:
        return datetime(
            year,
            month,
            day,
            tzinfo=ZoneInfo(timezone_name),
        )
    except ValueError:
        return None


def _channel_candidates(channel: Channel) -> tuple[str, ...]:
    """Return all known names and identifiers for one channel."""
    return (
        channel.source_id,
        channel.xmltv_id,
        *channel.aliases,
    )


def _match_channel_name(
    channel_name: str,
    channels: tuple[Channel, ...],
) -> Channel | None:
    """Match an RTVE channel label against the configured XMLTV channels."""
    normalised_name = _normalise(channel_name)

    if not normalised_name:
        return None

    for channel in channels:
        for candidate in _channel_candidates(channel):
            normalised_candidate = _normalise(candidate)

            if not normalised_candidate:
                continue

            if normalised_name == normalised_candidate:
                return channel

    # Handle common differences between RTVE labels and XMLTV IDs.
    known_names = {
        "la 1": ("la 1", "la.1.es"),
        "la 2": ("la 2", "la.2.es"),
        "24 horas": (
            "24 horas",
            "canal 24 horas",
            "canal 24 h",
            "canal.24.h.es",
        ),
        "canal 24 horas": (
            "24 horas",
            "canal 24 horas",
            "canal 24 h",
            "canal.24.h.es",
        ),
        "teledeporte": (
            "teledeporte",
            "teledeporte.es",
        ),
        "clan": (
            "clan",
            "clan tve",
            "clan.es",
        ),
    }

    aliases = known_names.get(normalised_name, (normalised_name,))

    for channel in channels:
        candidates = {
            _normalise(candidate) for candidate in _channel_candidates(channel) if candidate
        }

        if any(_normalise(alias) in candidates for alias in aliases):
            return channel

    return None


def _text(
    parent: Tag,
    selector: str,
) -> str:
    """Return cleaned text from the first matching element."""
    node = parent.select_one(selector)

    if node is None:
        return ""

    return node.get_text(" ", strip=True)


def _attribute_url(
    parent: Tag,
    selector: str,
    attribute: str,
    base_url: str,
) -> str:
    """Return an absolute URL from a selected HTML attribute."""
    node = parent.select_one(selector)

    if not isinstance(node, Tag):
        return ""

    value = node.get(attribute)

    if not isinstance(value, str) or not value.strip():
        return ""

    return urljoin(base_url, value.strip())


def _parse_time_range(
    value: str,
    schedule_date: datetime,
    timezone_name: str,
) -> tuple[datetime, datetime] | None:
    """Parse an RTVE time range such as '06:00-07:15'."""
    match = re.search(
        r"(\d{1,2}:\d{2})\s*[-–—]\s*(\d{1,2}:\d{2})",
        value,
    )

    if match is None:
        return None

    try:
        start_time = datetime.strptime(
            match.group(1),
            "%H:%M",
        ).time()

        stop_time = datetime.strptime(
            match.group(2),
            "%H:%M",
        ).time()
    except ValueError:
        return None

    timezone = ZoneInfo(timezone_name)

    start = datetime.combine(
        schedule_date.date(),
        start_time,
        timezone,
    )

    stop = datetime.combine(
        schedule_date.date(),
        stop_time,
        timezone,
    )

    # A programme ending after midnight belongs to the next calendar day.
    if stop <= start:
        stop += timedelta(days=1)

    return start, stop


def _find_schedule_date(
    node: Tag,
    timezone_name: str,
) -> datetime | None:
    """
    Find the date associated with a programme node.

    RTVE may place the date on the containing schedule section rather than
    directly on each programme.
    """
    current: Tag | None = node

    while current is not None:
        for selector in (
            "h2[aria-label]",
            "h3[aria-label]",
            "[data-date]",
            ".datemi",
        ):
            candidate = current.select_one(selector)

            if not isinstance(candidate, Tag):
                continue

            label = (
                candidate.get("aria-label")
                or candidate.get("data-date")
                or candidate.get_text(" ", strip=True)
            )

            parsed = _parse_schedule_date(
                str(label),
                timezone_name,
            )

            if parsed is not None:
                return parsed

        parent = current.parent
        current = parent if isinstance(parent, Tag) else None

    return None


def _programme_from_node(
    node: Tag,
    config: SourceConfig,
) -> Programme | None:
    """Convert one RTVE schedule element into a Programme object."""
    channel_name = _text(node, ".cademi")

    if not channel_name:
        channel_name = str(node.get("data-channel") or node.get("data-canal") or "")

    channel = _match_channel_name(
        channel_name,
        config.channels,
    )

    if channel is None:
        return None

    title = _text(node, ".maintitle")

    if not title:
        title = str(node.get("data-title") or "").strip()

    if not title:
        return None

    time_range = _text(node, ".horemi")

    if not time_range:
        start_value = str(node.get("data-start") or node.get("data-inicio") or "")
        stop_value = str(node.get("data-end") or node.get("data-fin") or "")

        if start_value and stop_value:
            time_range = f"{start_value}-{stop_value}"

    schedule_date = _find_schedule_date(
        node,
        config.timezone,
    )

    if schedule_date is None:
        return None

    parsed_times = _parse_time_range(
        time_range,
        schedule_date,
        config.timezone,
    )

    if parsed_times is None:
        return None

    start, stop = parsed_times

    description = _text(node, ".txtBox > p")

    if not description:
        description = _text(node, ".description")

    category = _text(node, ".genre")

    if not category:
        category = _text(node, ".category")

    programme_url = _attribute_url(
        node,
        "a.goto_media[href]",
        "href",
        config.homepage,
    )

    if not programme_url:
        programme_url = _attribute_url(
            node,
            "a[href]",
            "href",
            config.homepage,
        )

    icon = _attribute_url(
        node,
        "img[src]",
        "src",
        config.homepage,
    )

    if not icon:
        icon = _attribute_url(
            node,
            "img[data-src]",
            "data-src",
            config.homepage,
        )

    return Programme(
        channel_id=channel.xmltv_id,
        start=start,
        stop=stop,
        title=title,
        description=description,
        category=category,
        url=programme_url,
        icon=icon,
    )


def parse_page(
    page: str,
    config: SourceConfig,
) -> list[Programme]:
    """Parse RTVE's public programme-guide HTML."""
    soup = BeautifulSoup(page, "html.parser")

    found: dict[
        tuple[str, datetime, str],
        Programme,
    ] = {}

    selectors = (
        ".mod.video_mod.sched",
        ".video_mod.sched",
        ".sched",
        "[data-channel][data-start]",
        "[data-canal][data-inicio]",
    )

    seen_nodes: set[int] = set()

    for selector in selectors:
        for node in soup.select(selector):
            if not isinstance(node, Tag):
                continue

            node_identity = id(node)

            if node_identity in seen_nodes:
                continue

            seen_nodes.add(node_identity)

            programme = _programme_from_node(
                node,
                config,
            )

            if programme is None:
                continue

            key = (
                programme.channel_id,
                programme.start,
                programme.title,
            )

            found[key] = programme

    return sorted(
        found.values(),
        key=lambda programme: (
            programme.start,
            programme.channel_id,
            programme.title,
        ),
    )


class Adapter:
    """RTVE source adapter used by the common guide builder."""

    def fetch_and_parse(
        self,
        config: SourceConfig,
    ) -> list[Programme]:
        guide_url = str(
            config.options.get(
                "guide_url",
                config.homepage,
            )
        )

        page = _fetch(guide_url)

        print(
            f"Downloaded {len(page)} characters from {guide_url}",
            flush=True,
        )

        programmes = parse_page(
            page,
            config,
        )

        channel_count = len({programme.channel_id for programme in programmes})

        print(
            f"Parsed {len(programmes)} programmes across {channel_count} channels",
            flush=True,
        )

        return programmes
