from __future__ import annotations

from datetime import datetime

from bs4 import BeautifulSoup, Tag

from ...core.http import fetch_text
from ...core.models import GuideConfig, Programme, ProviderConfig
from ...core.source import SourceProvider
from .common import match_channel, parse_absolute_date, programme_from_node, text


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


class NationalProvider(SourceProvider):
    def fetch(self, guide: GuideConfig, provider: ProviderConfig) -> list[Programme]:
        url = str(provider.options.get("url", guide.homepage))
        return parse_page(fetch_text(url), guide)
