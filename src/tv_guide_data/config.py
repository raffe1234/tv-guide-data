from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import Channel


@dataclass(frozen=True)
class SourceConfig:
    key: str
    adapter: str
    name: str
    homepage: str
    output: Path
    timezone: str
    minimum_programmes: int
    minimum_channels: int
    channels: tuple[Channel, ...]
    options: dict[str, Any]


def load_source_config(path: Path) -> SourceConfig:
    raw = json.loads(path.read_text(encoding="utf-8"))
    channels = tuple(
        Channel(
            xmltv_id=item["xmltv_id"],
            name=item["name"],
            aliases=tuple(item.get("aliases", [])),
            source_id=item.get("source_id", ""),
        )
        for item in raw["channels"]
    )
    validation = raw.get("validation", {})
    return SourceConfig(
        key=raw["key"],
        adapter=raw["adapter"],
        name=raw["name"],
        homepage=raw["homepage"],
        output=Path(raw["output"]),
        timezone=raw["timezone"],
        minimum_programmes=int(validation.get("minimum_programmes", 1)),
        minimum_channels=int(validation.get("minimum_channels", 1)),
        channels=channels,
        options=dict(raw.get("options", {})),
    )
