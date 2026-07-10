import xml.etree.ElementTree as ET
from pathlib import Path

from tv_guide_data.config import load_source_config
from tv_guide_data.sources.rtve import parse_page
from tv_guide_data.xmltv import build_xml


def test_rtve_fixture() -> None:
    config = load_source_config(Path("config/sources/rtve.json"))
    page = Path("tests/fixtures/rtve.html").read_text(encoding="utf-8")
    programmes = parse_page(page, config)
    assert len(programmes) == 3
    assert {item.channel_id for item in programmes} == {
        "La.1.es",
        "La.2.es",
        "Teledeporte.es",
    }
    ET.fromstring(build_xml(config.channels, programmes, "test", config.homepage))
