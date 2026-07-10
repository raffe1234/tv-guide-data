from datetime import timedelta
from pathlib import Path

from tv_guide_data.config import load_source_config
from tv_guide_data.sources.rtve import parse_page


def test_rtve_fixture() -> None:
    config = load_source_config(Path("config/sources/rtve.json"))
    page = Path("tests/fixtures/rtve.html").read_text(encoding="utf-8")

    programmes = parse_page(page, config)

    assert len(programmes) == 3

    by_title = {programme.title: programme for programme in programmes}

    assert set(by_title) == {
        "Telediario Matinal",
        "Documental",
        "Estudio Estadio",
    }

    assert by_title["Telediario Matinal"].channel_id == "La.1.es"
    assert by_title["Documental"].channel_id == "La.2.es"
    assert by_title["Estudio Estadio"].channel_id == "Teledeporte.es"

    assert by_title["Telediario Matinal"].description == ("Morning news from RTVE.")

    assert by_title["Telediario Matinal"].url.endswith("/play/videos/telediario-matinal/")

    # The final programme crosses midnight.
    sports_programme = by_title["Estudio Estadio"]
    assert sports_programme.stop - sports_programme.start == timedelta(hours=1)
    assert sports_programme.stop.date() > sports_programme.start.date()
