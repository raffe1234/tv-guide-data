from __future__ import annotations

import html
import json
import logging
import re
from collections.abc import Iterable, Mapping
from datetime import datetime, timedelta
from typing import Any, cast
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup, Tag

from ...core.http import fetch_text
from ...core.models import GuideConfig, Programme, ProviderConfig
from ...core.source import SourceProvider
from .common import match_channel, parse_absolute_date, programme_from_node, text

LOGGER = logging.getLogger(__name__)

NATIONAL_CHANNEL_IDS = (
    "La.1.es",
    "La.2.es",
    "Canal.24.h.es",
    "Teledeporte.es",
)

_FLIGHT_PREFIXES = (
    "self.__next_f.push(",
    "self.__next_f__.push(",
)


def _clean(value: object) -> str:
    return re.sub(r"\s+", " ", html.unescape(str(value or ""))).strip()


def _identifier(value: object) -> str:
    if value is None or isinstance(value, bool):
        return ""

    if isinstance(value, (int, float)):
        number = int(value)
        return str(number) if number > 0 else ""

    result = str(value).strip()
    return result if result and result != "0" else ""


def _compact_datetime(value: object, timezone_name: str) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None

    try:
        parsed = datetime.strptime(raw, "%Y%m%d%H%M%S")
    except ValueError:
        return None

    return parsed.replace(tzinfo=ZoneInfo(timezone_name))


def _find_schedule_data(value: object) -> list[Mapping[str, Any]] | None:
    if isinstance(value, Mapping):
        candidate = value.get("data")
        if isinstance(candidate, list) and any(
            isinstance(item, Mapping) and "nombreCanal" in item and "items" in item
            for item in candidate
        ):
            return [
                cast(Mapping[str, Any], item) for item in candidate if isinstance(item, Mapping)
            ]

        for nested in value.values():
            found = _find_schedule_data(nested)
            if found is not None:
                return found

    if isinstance(value, list):
        for nested in value:
            found = _find_schedule_data(nested)
            if found is not None:
                return found

    return None


def _embedded_schedule(page: str) -> list[Mapping[str, Any]] | None:
    soup = BeautifulSoup(page, "html.parser")

    for script in soup.find_all("script"):
        content = script.string
        if content is None:
            content = script.get_text()

        raw = str(content).strip()
        if "wrapper schedBox" not in raw:
            continue

        if raw.endswith(";"):
            raw = raw[:-1]

        prefix = next(
            (candidate for candidate in _FLIGHT_PREFIXES if raw.startswith(candidate)),
            None,
        )
        if prefix is None or not raw.endswith(")"):
            continue

        try:
            outer: object = json.loads(raw[len(prefix) : -1])
        except json.JSONDecodeError:
            continue

        if not isinstance(outer, list) or len(outer) < 2 or not isinstance(outer[1], str):
            continue

        _, separator, payload_text = outer[1].partition(":")
        if not separator:
            continue

        try:
            payload: object = json.loads(payload_text.strip())
        except json.JSONDecodeError:
            continue

        found = _find_schedule_data(payload)
        if found is not None:
            return found

    return None


def _programme_url_and_icon(item: Mapping[str, Any]) -> tuple[str, str]:
    asset_id = _identifier(item.get("idAsset"))
    if asset_id:
        return (
            f"https://www.rtve.es/v/{asset_id}",
            f"https://img.rtve.es/v/{asset_id}?w=400",
        )

    programme_id = _identifier(item.get("idPrograma"))
    if programme_id:
        return (
            f"https://www.rtve.es/pr/{programme_id}",
            f"https://img.rtve.es/p/{programme_id}/imgportada?w=400",
        )

    return "", ""


def _parse_embedded_schedule(
    blocks: Iterable[Mapping[str, Any]],
    guide: GuideConfig,
    channel_ids: tuple[str, ...],
) -> list[Programme]:
    allowed_ids = set(channel_ids)
    found: dict[tuple[str, datetime, datetime, str], Programme] = {}

    for block in blocks:
        channel = match_channel(_clean(block.get("nombreCanal")), guide.channels)
        if channel is None or channel.xmltv_id not in allowed_ids:
            continue

        items = block.get("items")
        if not isinstance(items, list):
            continue

        for raw_item in items:
            if not isinstance(raw_item, Mapping):
                continue

            item = cast(Mapping[str, Any], raw_item)
            start = _compact_datetime(item.get("begintime"), guide.timezone)
            stop = _compact_datetime(item.get("endtime"), guide.timezone)
            title = _clean(item.get("original_event_name")) or _clean(item.get("name"))

            if start is None or stop is None or stop <= start or not title:
                continue

            url, icon = _programme_url_and_icon(item)
            programme = Programme(
                channel_id=channel.xmltv_id,
                start=start,
                stop=stop,
                title=title,
                description=_clean(item.get("description")),
                url=url,
                icon=icon,
            )
            found[(programme.channel_id, start, stop, title)] = programme

    return sorted(found.values(), key=lambda item: (item.start, item.channel_id, item.title))


def _parse_legacy_schedule(
    page: str,
    guide: GuideConfig,
    channel_ids: tuple[str, ...],
) -> list[Programme]:
    soup = BeautifulSoup(page, "html.parser")
    allowed_ids = set(channel_ids)
    found: dict[tuple[str, datetime, datetime, str], Programme] = {}

    for section in soup.select(".tvSchedule"):
        if not isinstance(section, Tag):
            continue

        heading = section.select_one("h2[aria-label], h3[aria-label]")
        if not isinstance(heading, Tag):
            continue

        label = str(heading.get("aria-label") or heading.get_text(" ", strip=True))
        schedule_date = parse_absolute_date(label, guide.timezone)
        if schedule_date is None:
            continue

        for node in section.select(".mod.video_mod.sched, .video_mod.sched, .sched"):
            if not isinstance(node, Tag):
                continue

            channel = match_channel(text(node, ".cademi"), guide.channels)
            if channel is None or channel.xmltv_id not in allowed_ids:
                continue

            programme = programme_from_node(
                node,
                channel=channel,
                day=schedule_date.date(),
                timezone_name=guide.timezone,
                base_url=guide.homepage,
            )
            if programme:
                found[
                    (
                        programme.channel_id,
                        programme.start,
                        programme.stop,
                        programme.title,
                    )
                ] = programme

    return sorted(found.values(), key=lambda item: (item.start, item.channel_id, item.title))


def parse_page(
    page: str,
    guide: GuideConfig,
    channel_ids: tuple[str, ...] = NATIONAL_CHANNEL_IDS,
) -> list[Programme]:
    embedded = _embedded_schedule(page)
    if embedded is not None:
        return _parse_embedded_schedule(embedded, guide, channel_ids)

    return _parse_legacy_schedule(page, guide, channel_ids)


def parse_pages(
    pages: Iterable[str],
    guide: GuideConfig,
    channel_ids: tuple[str, ...] = NATIONAL_CHANNEL_IDS,
) -> list[Programme]:
    found: dict[tuple[str, datetime, datetime, str], Programme] = {}

    for page in pages:
        for programme in parse_page(page, guide, channel_ids):
            key = (
                programme.channel_id,
                programme.start,
                programme.stop,
                programme.title,
            )
            found[key] = programme

    return sorted(found.values(), key=lambda item: (item.start, item.channel_id, item.title))


def _provider_urls(provider: ProviderConfig, fallback_url: str) -> tuple[str, ...]:
    configured = provider.options.get("urls")
    if configured is None:
        url = str(provider.options.get("url", fallback_url)).strip()
        if not url:
            raise ValueError("RTVE national provider URL is empty")
        return (url,)

    if not isinstance(configured, list) or not configured:
        raise ValueError("RTVE national provider option 'urls' must be a non-empty list")

    urls: list[str] = []
    for value in configured:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("RTVE national provider URLs must be non-empty strings")
        urls.append(value.strip())

    return tuple(urls)


def _provider_channel_ids(provider: ProviderConfig) -> tuple[str, ...]:
    configured = provider.options.get("channel_ids")
    if configured is None:
        return NATIONAL_CHANNEL_IDS

    if not isinstance(configured, list) or not configured:
        raise ValueError("RTVE national provider option 'channel_ids' must be a non-empty list")

    channel_ids: list[str] = []
    for value in configured:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("RTVE national channel ids must be non-empty strings")
        channel_ids.append(value.strip())

    return tuple(channel_ids)


def _past_hours(provider: ProviderConfig) -> float:
    raw = provider.options.get("past_hours", 12)
    if isinstance(raw, bool) or not isinstance(raw, (int, float, str)):
        raise ValueError("RTVE national provider past_hours must be numeric")

    try:
        value = float(raw)
    except ValueError as error:
        raise ValueError("RTVE national provider past_hours must be numeric") from error

    if value < 0:
        raise ValueError("RTVE national provider past_hours must not be negative")

    return value


class NationalProvider(SourceProvider):
    def fetch(self, guide: GuideConfig, provider: ProviderConfig) -> list[Programme]:
        channel_ids = _provider_channel_ids(provider)
        pages: list[str] = []

        for url in _provider_urls(provider, guide.homepage):
            page = fetch_text(url)
            page_programmes = parse_page(page, guide, channel_ids)
            LOGGER.info(
                "RTVE national page %s returned %d full-schedule programmes",
                url,
                len(page_programmes),
            )
            pages.append(page)

        programmes = parse_pages(pages, guide, channel_ids)
        reference = datetime.now(ZoneInfo(guide.timezone))
        cutoff = reference - timedelta(hours=_past_hours(provider))
        filtered = [programme for programme in programmes if programme.stop >= cutoff]

        LOGGER.info(
            "RTVE national provider kept %d programmes after the history cutoff",
            len(filtered),
        )
        return filtered
