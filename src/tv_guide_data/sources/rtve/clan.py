from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup, Tag

from ...core.http import fetch_text
from ...core.models import GuideConfig, Programme, ProviderConfig
from ...core.source import SourceProvider
from .common import match_channel, parse_relative_date, programme_from_node, text


def parse_page(page: str, guide: GuideConfig, now: datetime | None = None) -> list[Programme]:
    local_now = (now or datetime.now(tz=UTC)).astimezone(ZoneInfo(guide.timezone))
    soup = BeautifulSoup(page, "html.parser")
    channel = match_channel("Clan", guide.channels)
    if channel is None:
        return []

    found: dict[tuple[str, datetime, str], Programme] = {}
    for node in soup.select(".mod.video_mod.sched, .video_mod.sched, .sched"):
        if not isinstance(node, Tag):
            continue
        channel_label = text(node, ".cademi")
        if channel_label and match_channel(channel_label, (channel,)) is None:
            continue
        relative_label = text(node, ".datemi") or str(node.get("data-date") or "")
        day = parse_relative_date(relative_label, local_now)
        if day is None:
            continue
        programme = programme_from_node(
            node,
            channel=channel,
            day=day,
            timezone_name=guide.timezone,
            base_url=guide.homepage,
        )
        if programme:
            found[(programme.channel_id, programme.start, programme.title)] = programme

    return sorted(found.values(), key=lambda item: (item.start, item.title))


class ClanProvider(SourceProvider):
    def fetch(self, guide: GuideConfig, provider: ProviderConfig) -> list[Programme]:
        url = str(provider.options["url"])
        return parse_page(fetch_text(url), guide)
