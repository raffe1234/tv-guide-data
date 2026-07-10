from __future__ import annotations

import gzip
from datetime import datetime
from pathlib import Path
from typing import cast
from xml.etree import ElementTree as ET

from .models import GuideConfig, Programme


def _timestamp(value: datetime) -> str:
    return value.strftime("%Y%m%d%H%M%S %z")


def validate(config: GuideConfig, programmes: list[Programme]) -> None:
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
