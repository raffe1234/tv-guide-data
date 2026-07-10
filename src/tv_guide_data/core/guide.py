from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime

from .models import GuideConfig, Programme
from .source import load_provider

LOGGER = logging.getLogger(__name__)


def build_programmes(config: GuideConfig) -> list[Programme]:
    collected: list[Programme] = []
    for provider_config in config.providers:
        provider = load_provider(provider_config.adapter)
        LOGGER.info("Running provider %s", provider_config.adapter)
        programmes = provider.fetch(config, provider_config)
        LOGGER.info("Provider returned %d programmes", len(programmes))
        collected.extend(programmes)

    deduplicated: dict[tuple[str, datetime, datetime, str], Programme] = {}
    for programme in collected:
        key = (programme.channel_id, programme.start, programme.stop, programme.title)
        deduplicated[key] = programme

    result = sorted(
        deduplicated.values(),
        key=lambda item: (item.start, item.channel_id, item.title),
    )
    counts = Counter(item.channel_id for item in result)
    LOGGER.info("Combined result: %d programmes across %d channels", len(result), len(counts))
    for channel_id, count in sorted(counts.items()):
        LOGGER.info("  %s: %d", channel_id, count)
    return result
