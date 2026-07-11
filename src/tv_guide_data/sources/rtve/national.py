from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import datetime

from bs4 import BeautifulSoup, Tag

from ...core.http import fetch_text
from ...core.models import GuideConfig, Programme, ProviderConfig
from ...core.source import SourceProvider
from .common import match_channel, parse_absolute_date, programme_from_node, text

LOGGER = logging.getLogger(__name__)


def parse_page(page: str, guide: GuideConfig) -> list[Programme]:
    soup = BeautifulSoup(page, "html.parser")
    found: dict[tuple[str, datetime, str], Programme] = {}

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
            if channel is None:
                continue

            programme = programme_from_node(
                node,
                channel=channel,
                day=schedule_date.date(),
                timezone_name=guide.timezone,
                base_url=guide.homepage,
            )
            if programme:
                found[(programme.channel_id, programme.start, programme.title)] = programme

    return sorted(found.values(), key=lambda item: (item.start, item.channel_id, item.title))


def parse_pages(pages: Iterable[str], guide: GuideConfig) -> list[Programme]:
    found: dict[tuple[str, datetime, datetime, str], Programme] = {}

    for page in pages:
        for programme in parse_page(page, guide):
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


class NationalProvider(SourceProvider):
    def fetch(self, guide: GuideConfig, provider: ProviderConfig) -> list[Programme]:
        pages: list[str] = []

        for url in _provider_urls(provider, guide.homepage):
            page = fetch_text(url)
            page_programmes = parse_page(page, guide)
            LOGGER.info("RTVE national page %s returned %d programmes", url, len(page_programmes))
            pages.append(page)

        return parse_pages(pages, guide)
