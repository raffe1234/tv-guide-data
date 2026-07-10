from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import Channel, GuideConfig, ProviderConfig


def _required_string(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Missing or invalid string: {key}")
    return value.strip()


def load_guide_config(path: Path) -> GuideConfig:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))

    channels = tuple(
        Channel(
            xmltv_id=_required_string(item, "xmltv_id"),
            display_name=_required_string(item, "display_name"),
            source_id=str(item.get("source_id", "")),
            aliases=tuple(str(value) for value in item.get("aliases", [])),
        )
        for item in data.get("channels", [])
    )
    providers = tuple(
        ProviderConfig(
            adapter=_required_string(item, "adapter"),
            options=dict(item.get("options", {})),
        )
        for item in data.get("providers", [])
    )
    if not channels:
        raise ValueError(f"No channels configured in {path}")
    if not providers:
        raise ValueError(f"No providers configured in {path}")

    return GuideConfig(
        name=_required_string(data, "name"),
        output_name=_required_string(data, "output_name"),
        homepage=_required_string(data, "homepage"),
        timezone=_required_string(data, "timezone"),
        language=_required_string(data, "language"),
        minimum_programmes=int(data.get("minimum_programmes", 1)),
        channels=channels,
        providers=providers,
    )
