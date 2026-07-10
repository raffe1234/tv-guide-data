#!/usr/bin/env python3
from __future__ import annotations

import argparse
import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from tv_guide_data.config import load_source_config
from tv_guide_data.sources import load_adapter
from tv_guide_data.xmltv import build_xml, validate, write_files


def build(config_path: Path) -> None:
    config = load_source_config(config_path)
    logging.info("Building %s from %s", config.name, config_path)
    adapter = load_adapter(config.adapter)
    programmes = adapter.fetch_and_parse(config)
    logging.info(
        "Found %d programmes across %d channels",
        len(programmes),
        len({item.channel_id for item in programmes}),
    )
    validate(
        programmes,
        config.minimum_programmes,
        config.minimum_channels,
        datetime.now(ZoneInfo(config.timezone)),
    )
    xml = build_xml(config.channels, programmes, "tv-guide-data", config.homepage)
    plain, compressed = write_files(xml, config.output)
    logging.info("Wrote %s and %s", plain, compressed)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build one or more XMLTV guides.")
    parser.add_argument(
        "configs",
        nargs="*",
        type=Path,
        help="Source configuration files. Defaults to config/sources/*.json.",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    configs = args.configs or sorted(Path("config/sources").glob("*.json"))
    if not configs:
        raise RuntimeError("No source configuration files were found.")
    for config_path in configs:
        build(config_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
