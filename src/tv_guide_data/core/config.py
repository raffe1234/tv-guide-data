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


def _configured_ids(channels: tuple[Channel, ...]) -> set[str]:
    return {channel.xmltv_id for channel in channels}


def _load_channel_validation(
    data: dict[str, Any], channels: tuple[Channel, ...], path: Path
) -> tuple[tuple[str, ...], int]:
    raw_validation = data.get("channel_validation", {})
    if not isinstance(raw_validation, dict):
        raise ValueError(f"Invalid channel_validation in {path}")

    raw_required = raw_validation.get("required", [])
    if not isinstance(raw_required, list) or not all(
        isinstance(value, str) and value.strip() for value in raw_required
    ):
        raise ValueError(f"Invalid channel_validation.required in {path}")

    required_channels = tuple(value.strip() for value in raw_required)
    minimum_per_channel = int(raw_validation.get("minimum_per_channel", 1))
    if minimum_per_channel < 1:
        raise ValueError("channel_validation.minimum_per_channel must be at least 1")

    unknown_ids = sorted(set(required_channels) - _configured_ids(channels))
    if unknown_ids:
        raise ValueError(f"Unknown required channel ids in {path}: {', '.join(unknown_ids)}")

    return required_channels, minimum_per_channel


def _load_coverage_validation(
    data: dict[str, Any], channels: tuple[Channel, ...], path: Path
) -> tuple[tuple[str, ...], float, float]:
    raw_validation = data.get("coverage_validation", {})
    if not isinstance(raw_validation, dict):
        raise ValueError(f"Invalid coverage_validation in {path}")

    raw_channels = raw_validation.get("channels", [])
    if not isinstance(raw_channels, list) or not all(
        isinstance(value, str) and value.strip() for value in raw_channels
    ):
        raise ValueError(f"Invalid coverage_validation.channels in {path}")

    coverage_channels = tuple(value.strip() for value in raw_channels)
    minimum_future_hours = float(raw_validation.get("minimum_future_hours", 0))
    maximum_gap_hours = float(raw_validation.get("maximum_gap_hours", 24))

    if coverage_channels and minimum_future_hours <= 0:
        raise ValueError("coverage_validation.minimum_future_hours must be greater than 0")
    if maximum_gap_hours <= 0:
        raise ValueError("coverage_validation.maximum_gap_hours must be greater than 0")

    unknown_ids = sorted(set(coverage_channels) - _configured_ids(channels))
    if unknown_ids:
        raise ValueError(f"Unknown coverage channel ids in {path}: {', '.join(unknown_ids)}")

    return coverage_channels, minimum_future_hours, maximum_gap_hours


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

    required_channels, minimum_per_channel = _load_channel_validation(data, channels, path)
    coverage_channels, minimum_future_hours, maximum_gap_hours = _load_coverage_validation(
        data, channels, path
    )

    return GuideConfig(
        name=_required_string(data, "name"),
        output_name=_required_string(data, "output_name"),
        homepage=_required_string(data, "homepage"),
        timezone=_required_string(data, "timezone"),
        language=_required_string(data, "language"),
        minimum_programmes=int(data.get("minimum_programmes", 1)),
        channels=channels,
        providers=providers,
        required_channels=required_channels,
        minimum_programmes_per_channel=minimum_per_channel,
        coverage_channels=coverage_channels,
        minimum_future_hours=minimum_future_hours,
        maximum_gap_hours=maximum_gap_hours,
    )
