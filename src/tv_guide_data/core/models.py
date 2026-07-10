from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True, slots=True)
class Channel:
    xmltv_id: str
    display_name: str
    source_id: str = ""
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Programme:
    channel_id: str
    start: datetime
    stop: datetime
    title: str
    description: str = ""
    category: str = ""
    url: str = ""
    icon: str = ""


@dataclass(frozen=True, slots=True)
class ProviderConfig:
    adapter: str
    options: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class GuideConfig:
    name: str
    output_name: str
    homepage: str
    timezone: str
    language: str
    minimum_programmes: int
    channels: tuple[Channel, ...]
    providers: tuple[ProviderConfig, ...]
