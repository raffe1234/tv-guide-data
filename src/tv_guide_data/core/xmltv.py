from __future__ import annotations

import gzip
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import cast
from xml.etree import ElementTree as ET
from zoneinfo import ZoneInfo

from .models import GuideConfig, Programme


def _timestamp(value: datetime) -> str:
    return value.strftime("%Y%m%d%H%M%S %z")


def _validate_future_coverage(
    config: GuideConfig,
    programmes: list[Programme],
    reference: datetime,
) -> None:
    for channel_id in config.coverage_channels:
        channel_programmes = sorted(
            (
                programme
                for programme in programmes
                if programme.channel_id == channel_id and programme.stop > reference
            ),
            key=lambda item: (item.start, item.stop, item.title),
        )

        cursor = reference
        for programme in channel_programmes:
            if programme.start > cursor:
                gap_hours = (programme.start - cursor).total_seconds() / 3600
                if gap_hours > config.maximum_gap_hours:
                    raise RuntimeError(
                        f"Channel {channel_id} has a future schedule gap of "
                        f"{gap_hours:.1f} hours; maximum is "
                        f"{config.maximum_gap_hours:.1f}."
                    )
            if programme.stop > cursor:
                cursor = programme.stop

        future_hours = max(0.0, (cursor - reference).total_seconds() / 3600)
        if future_hours < config.minimum_future_hours:
            raise RuntimeError(
                f"Channel {channel_id} has {future_hours:.1f} hours of future "
                f"coverage; minimum is {config.minimum_future_hours:.1f}."
            )


def validate(
    config: GuideConfig,
    programmes: list[Programme],
    *,
    now: datetime | None = None,
) -> None:
    if len(programmes) < config.minimum_programmes:
        raise RuntimeError(
            f"Only {len(programmes)} programmes were found; minimum is {config.minimum_programmes}."
        )

    valid_ids = {channel.xmltv_id for channel in config.channels}
    for programme in programmes:
        if programme.channel_id not in valid_ids:
            raise RuntimeError(f"Unknown channel id: {programme.channel_id}")
        if not programme.title.strip():
            raise RuntimeError("Programme title is empty")
        if programme.stop <= programme.start:
            raise RuntimeError(f"Invalid programme duration: {programme.title}")
        if programme.start.tzinfo is None or programme.stop.tzinfo is None:
            raise RuntimeError(f"Naive programme time: {programme.title}")

    counts = Counter(programme.channel_id for programme in programmes)
    for channel_id in config.required_channels:
        count = counts[channel_id]
        if count < config.minimum_programmes_per_channel:
            raise RuntimeError(
                f"Channel {channel_id} has {count} programmes; minimum is "
                f"{config.minimum_programmes_per_channel}."
            )

    if config.coverage_channels:
        reference = now or datetime.now(ZoneInfo(config.timezone))
        if reference.tzinfo is None:
            raise ValueError("Coverage validation reference time must be timezone-aware")
        _validate_future_coverage(config, programmes, reference)


def render(config: GuideConfig, programmes: list[Programme]) -> bytes:
    root = ET.Element(
        "tv",
        {
            "generator-info-name": "tv-guide-data",
            "generator-info-url": config.homepage,
        },
    )

    for channel in config.channels:
        node = ET.SubElement(root, "channel", {"id": channel.xmltv_id})
        ET.SubElement(node, "display-name", {"lang": config.language}).text = channel.display_name

    for programme in programmes:
        node = ET.SubElement(
            root,
            "programme",
            {
                "start": _timestamp(programme.start),
                "stop": _timestamp(programme.stop),
                "channel": programme.channel_id,
            },
        )
        ET.SubElement(node, "title", {"lang": config.language}).text = programme.title
        if programme.description:
            ET.SubElement(node, "desc", {"lang": config.language}).text = programme.description
        if programme.category:
            ET.SubElement(node, "category", {"lang": config.language}).text = programme.category
        if programme.url:
            ET.SubElement(node, "url").text = programme.url
        if programme.icon:
            ET.SubElement(node, "icon", {"src": programme.icon})

    ET.indent(root, space="  ")
    return cast(bytes, ET.tostring(root, encoding="utf-8", xml_declaration=True))


def write_files(output_dir: Path, output_name: str, xml_data: bytes) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    xml_path = output_dir / f"{output_name}.xml"
    gzip_path = output_dir / f"{output_name}.xml.gz"

    xml_path.write_bytes(xml_data)
    with gzip.GzipFile(filename=str(gzip_path), mode="wb", compresslevel=9, mtime=0) as handle:
        handle.write(xml_data)

    return xml_path, gzip_path
