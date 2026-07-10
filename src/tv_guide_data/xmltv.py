from __future__ import annotations

import gzip
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path

from .models import Channel, Programme


def _format_time(value: datetime) -> str:
    return value.strftime("%Y%m%d%H%M%S %z")


def build_xml(
    channels: tuple[Channel, ...],
    programmes: list[Programme],
    generator_name: str,
    generator_url: str,
) -> bytes:
    root = ET.Element(
        "tv",
        {"generator-info-name": generator_name, "generator-info-url": generator_url},
    )
    for channel in channels:
        node = ET.SubElement(root, "channel", {"id": channel.xmltv_id})
        ET.SubElement(node, "display-name").text = channel.name

    for programme in sorted(programmes, key=lambda item: (item.start, item.channel_id, item.title)):
        node = ET.SubElement(
            root,
            "programme",
            {
                "start": _format_time(programme.start),
                "stop": _format_time(programme.stop),
                "channel": programme.channel_id,
            },
        )
        ET.SubElement(node, "title").text = programme.title
        if programme.description:
            ET.SubElement(node, "desc").text = programme.description
        if programme.category:
            ET.SubElement(node, "category").text = programme.category
        if programme.url:
            ET.SubElement(node, "url").text = programme.url
        if programme.icon:
            ET.SubElement(node, "icon", {"src": programme.icon})

    ET.indent(root, space="  ")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def validate(
    programmes: list[Programme], minimum_programmes: int, minimum_channels: int, now: datetime
) -> None:
    active_channels = {item.channel_id for item in programmes}
    current_or_future = [item for item in programmes if item.stop > now - timedelta(hours=6)]
    if len(programmes) < minimum_programmes:
        raise RuntimeError(
            f"Only {len(programmes)} programmes were found; minimum is {minimum_programmes}."
        )
    if len(active_channels) < minimum_channels:
        raise RuntimeError(
            "Only "
            f"{len(active_channels)} channels contain programmes; "
            f"minimum is {minimum_channels}."
        )
    if not current_or_future:
        raise RuntimeError("The guide contains no current or future programmes.")


def write_files(xml: bytes, output: Path) -> tuple[Path, Path]:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_bytes(xml)
    ET.parse(temporary)
    temporary.replace(output)

    compressed = Path(f"{output}.gz")
    with (
        compressed.open("wb") as raw,
        gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=9, mtime=0) as archive,
    ):
        archive.write(xml)
    return output, compressed
