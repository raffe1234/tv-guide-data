from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup, Tag

from ...core.http import fetch_text
from ...core.models import Channel, GuideConfig, Programme, ProviderConfig
from ...core.source import SourceProvider
from .common import absolute_attribute, match_channel, text

LOGGER = logging.getLogger(__name__)

CHANNEL_OPTION_SELECTOR = "#filtro-canal option[value]"
PROGRAMME_SELECTOR = ".item[data-begindate][data-enddate]"


def _target_channels(guide: GuideConfig, channel_ids: tuple[str, ...]) -> tuple[Channel, ...]:
    requested = set(channel_ids)
    channels = tuple(channel for channel in guide.channels if channel.xmltv_id in requested)
    missing = sorted(requested - {channel.xmltv_id for channel in channels})
    if missing:
        raise ValueError(f"Unknown international channel ids: {', '.join(missing)}")
    return channels


def _attribute(node: Tag, name: str) -> str:
    value = node.get(name)
    return value.strip() if isinstance(value, str) else ""


def _parse_datetime(
    value: str,
    timezone_name: str,
    fallback_date: date | None = None,
) -> datetime | None:
    cleaned = " ".join(value.split())
    timezone = ZoneInfo(timezone_name)

    for format_string in ("%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M"):
        try:
            return datetime.strptime(cleaned, format_string).replace(tzinfo=timezone)
        except ValueError:
            continue

    if fallback_date is None:
        return None

    try:
        clock_time = datetime.strptime(cleaned, "%H:%M").time()
    except ValueError:
        return None

    return datetime.combine(fallback_date, clock_time, timezone)


def _programme_url(node: Tag, base_url: str) -> str:
    asset_id = _attribute(node, "data-asset")
    if asset_id and asset_id != "0":
        return urljoin(base_url, f"/v/{asset_id}")

    programme_id = _attribute(node, "data-programa")
    if programme_id and programme_id != "0":
        return urljoin(base_url, f"/pr/{programme_id}")

    return ""


def _programme_from_item(
    node: Tag,
    *,
    channel: Channel,
    timezone_name: str,
    base_url: str,
) -> Programme | None:
    start = _parse_datetime(_attribute(node, "data-begindate"), timezone_name)
    if start is None:
        return None

    stop = _parse_datetime(
        _attribute(node, "data-enddate"),
        timezone_name,
        fallback_date=start.date(),
    )
    if stop is None:
        return None
    if stop <= start:
        stop += timedelta(days=1)

    title = _attribute(node, "data-title") or text(node, ".maintitle")
    if not title:
        return None

    description = _attribute(node, "data-description") or text(node, ".cat-detalle")
    icon = absolute_attribute(node, "img.thumb[data-src]", "data-src", base_url)
    if not icon:
        icon = absolute_attribute(node, "img[data-src]", "data-src", base_url)
    if not icon:
        icon = absolute_attribute(node, "img[src]", "src", base_url)

    return Programme(
        channel_id=channel.xmltv_id,
        start=start,
        stop=stop,
        title=title,
        description=description,
        url=_programme_url(node, base_url),
        icon=icon,
    )


def _channel_rows(
    soup: BeautifulSoup,
    channels: tuple[Channel, ...],
) -> list[tuple[Channel, Tag]]:
    rows: list[tuple[Channel, Tag]] = []
    seen: set[tuple[str, str]] = set()

    for option in soup.select(CHANNEL_OPTION_SELECTOR):
        if not isinstance(option, Tag):
            continue

        channel = match_channel(option.get_text(" ", strip=True), channels)
        row_key = _attribute(option, "value")
        if channel is None or not row_key:
            continue

        unique_key = (channel.xmltv_id, row_key)
        if unique_key in seen:
            continue
        seen.add(unique_key)

        row = soup.find(id=f"row-guia-{row_key}")
        if isinstance(row, Tag):
            rows.append((channel, row))

    return rows


def parse_page(
    page: str,
    guide: GuideConfig,
    channel_ids: tuple[str, ...],
    now: datetime | None = None,
) -> list[Programme]:
    del now  # The international page provides absolute dates for every programme.

    channels = _target_channels(guide, channel_ids)
    soup = BeautifulSoup(page, "html.parser")
    rows = _channel_rows(soup, channels)

    found: dict[tuple[str, datetime, datetime, str], Programme] = {}
    candidate_count = 0
    invalid_count = 0

    for channel, row in rows:
        for node in row.select(PROGRAMME_SELECTOR):
            if not isinstance(node, Tag):
                continue
            candidate_count += 1

            programme = _programme_from_item(
                node,
                channel=channel,
                timezone_name=guide.timezone,
                base_url=guide.homepage,
            )
            if programme is None:
                invalid_count += 1
                continue

            key = (
                programme.channel_id,
                programme.start,
                programme.stop,
                programme.title,
            )
            found[key] = programme

    LOGGER.info(
        "International parser inspected %d candidates across %d channel rows: "
        "%d programmes, %d invalid",
        candidate_count,
        len(rows),
        len(found),
        invalid_count,
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
