from __future__ import annotations

import argparse
import logging
from pathlib import Path

from tv_guide_data.core.config import load_guide_config
from tv_guide_data.core.guide import build_programmes
from tv_guide_data.core.xmltv import render, validate, write_files


def build(config_path: Path, output_dir: Path) -> list[str]:
    config = load_guide_config(config_path)
    logging.info("Building %s from %s", config.name, config_path)
    programmes = build_programmes(config)
    warnings = validate(config, programmes)
    for warning in warnings:
        logging.warning("%s", warning)
    xml_path, gzip_path = write_files(
        output_dir,
        config.output_name,
        render(config, programmes),
    )
    logging.info("Wrote %s and %s", xml_path, gzip_path)
    return [f"{config.name}: {warning}" for warning in warnings]


def _write_warning_file(path: Path, warnings: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(warnings)
    if content:
        content += "\n"
    path.write_text(content, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config-dir", type=Path, default=Path("config/guides"))
    parser.add_argument("--output-dir", type=Path, default=Path("output"))
    parser.add_argument("--warning-file", type=Path)
    arguments = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    paths = sorted(arguments.config_dir.glob("*.json"))
    if not paths:
        raise RuntimeError(f"No guide configurations found in {arguments.config_dir}")

    warnings: list[str] = []
    for path in paths:
        warnings.extend(build(path, arguments.output_dir))

    if arguments.warning_file is not None:
        _write_warning_file(arguments.warning_file, warnings)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
