from pathlib import Path

from tv_guide_data.core.config import load_guide_config
from tv_guide_data.sources.rtve.national import parse_page


def test_national_fixture() -> None:
    guide = load_guide_config(Path("config/guides/rtve.json"))
    page = Path("tests/fixtures/rtve-national.html").read_text(encoding="utf-8")
    programmes = parse_page(page, guide)
    assert len(programmes) == 2
    assert programmes[0].channel_id == "La.1.es"
    assert programmes[1].stop.date() > programmes[1].start.date()
