# tv-guide-data

`tv-guide-data` builds small XMLTV guides from official broadcaster pages.
The first supported guide is RTVE Spain.

## Published guide

```text
https://raw.githubusercontent.com/raffe1234/tv-guide-data/main/output/rtve.xml.gz
```

## Current RTVE coverage

| XMLTV id | Channel | Source |
|---|---|---|
| `La.1.es` | La 1 | RTVE TV guide |
| `La.2.es` | La 2 | RTVE TV guide |
| `Canal.24.h.es` | Canal 24 Horas | RTVE TV guide |
| `Teledeporte.es` | Teledeporte | RTVE TV guide |
| `Clan.es` | Clan | Dedicated Clan schedule |

The international channels are configured as future targets, but are not
published until a reliable full schedule source is available:
`TVE.Internacional.es`, `Star.es`, and `Clan.Internacional.es`.

## Architecture

- `core/`: configuration, HTTP, validation, XMLTV output and plugin loading.
- `sources/`: broadcaster-specific source plugins.
- `config/guides/`: declarative guide definitions.
- `scripts/build.py`: builds all configured guides.

An RTVE guide is assembled from independent providers:

- `rtve.national` parses the national RTVE guide.
- `rtve.clan` parses the dedicated Clan schedule.
- future providers can be added without changing the XMLTV writer.

## Run locally

```bash
python -m pip install -e ".[dev]"
python scripts/build.py
pytest
ruff check .
ruff format --check .
mypy
```

On systems where the package is not installed:

```bash
PYTHONPATH=src python scripts/build.py
```

## GitHub Actions

- `Test` checks formatting, linting, typing and tests.
- `Update TV guides` runs twice daily, validates the output and commits changed
  XML/XML.GZ files.

## Adding a provider

See [CONTRIBUTING.md](CONTRIBUTING.md).
