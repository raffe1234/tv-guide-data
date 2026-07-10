from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Channel:
    xmltv_id: str
    name: str
    aliases: tuple[str, ...] = ()
    source_id: str = ""


@dataclass(frozen=True)
class Programme:
    channel_id: str
    start: datetime
    stop: datetime
    title: str
    description: str = ""
    category: str = ""
    url: str = ""
    icon: str = ""
