from __future__ import annotations

import argparse
import logging
from pathlib import Path

from tv_guide_data.core.config import load_guide_config
from tv_guide_data.core.guide import build_programmes
from tv_guide_data.core.xmltv import render, validate, write_files


def build(config_path: Path, output_dir: Path) -> None:
    config = load_guide_config(config_path)
    logging.info("Building %s from %s", config.name, config_path)
    programmes = build_programmes(config)
    validate(config, programmes)
    xml_path, gzip_path = write_files(
        output_dir,
        config.output_name,
        render(config, programmes),
    )
    logging.info("Wrote %s and %s", xml_path, gzip_path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config-dir", type=Path, default=Path("config/guides"))
    parser.add_argument("--output-dir", type=Path, default=Path("output"))
    arguments = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    paths = sorted(arguments.config_dir.glob("*.json"))
    if not paths:
        raise RuntimeError(f"No guide configurations found in {arguments.config_dir}")
    for path in paths:
        build(path, arguments.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
