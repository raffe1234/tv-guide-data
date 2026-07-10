# tv-guide-data

A modular, community-friendly project that builds XMLTV programme guides from official or clearly permitted public TV schedule sources and publishes them automatically with GitHub Actions.

The first supported provider is **RTVE** in Spain. The architecture is deliberately source-based, so providers such as **SVT**, NRK, DR, or Yle can be added without rewriting the shared XMLTV, validation, compression, or publishing code.

## Published guides

After the first successful workflow run, replace `YOUR-GITHUB-USERNAME`:

```text
https://raw.githubusercontent.com/YOUR-GITHUB-USERNAME/tv-guide-data/main/output/rtve.xml.gz
```

Uncompressed version:

```text
https://raw.githubusercontent.com/YOUR-GITHUB-USERNAME/tv-guide-data/main/output/rtve.xml
```

## Supported RTVE channels

| Channel | XMLTV ID |
|---|---|
| La 1 | `La.1.es` |
| La 2 | `La.2.es` |
| Canal 24 Horas | `Canal.24.h.es` |
| Teledeporte | `Teledeporte.es` |
| Clan | `Clan.es` |

The IDs are kept stable so they can match `tvg-id` values in IPTV playlists. The project does not invent schedules for channels that are absent from the official source.

## Repository layout

```text
config/sources/          Source and channel configuration
src/tv_guide_data/       Shared models, XMLTV and validation code
src/tv_guide_data/sources/
                         One adapter per schedule provider
scripts/build.py         Builds one source or every configured source
tests/                   Offline parser fixtures and tests
output/                  Published XML and compressed XMLTV files
.github/workflows/       Tests and scheduled guide updates
```

## First GitHub setup

1. Create a **public** repository named `tv-guide-data`.
2. Create it without a generated README, `.gitignore`, or licence because those files are included here.
3. Upload every file and folder from this package to the repository root, including `.github`.
4. Open **Actions**, select **Update TV guides**, and choose **Run workflow**.
5. After the workflow succeeds, verify that `output/rtve.xml` and `output/rtve.xml.gz` appear in the repository.
6. Use the raw `.xml.gz` URL in Kodi or another XMLTV-compatible application.

The update workflow runs twice per day. It tests the code, downloads current schedule data, validates the result, and commits files only when they changed. A failed or suspiciously small guide is not published.

## Kodi

In **PVR IPTV Simple Client**, use:

```text
https://raw.githubusercontent.com/YOUR-GITHUB-USERNAME/tv-guide-data/main/output/rtve.xml.gz
```

Then clear existing guide data and restart Kodi.

## Local development

Python 3.11 or later is required.

```bash
python -m venv .venv
python -m pip install -e ".[dev]"
```

Activate the environment and run:

```bash
ruff check .
ruff format --check .
mypy
pytest
python scripts/build.py
```

To install the optional local Git hooks:

```bash
pre-commit install
```

## Adding a provider

Each provider normally needs:

1. `config/sources/<provider>.json`
2. `src/tv_guide_data/sources/<provider>.py`
3. An offline fixture and parser test in `tests/`

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Project status

This project is at an early alpha stage. Source websites and APIs can change without notice, so failures should be expected and reported with a workflow link or a reproducible test fixture.

## Licence

The code is MIT licensed. Programme data remains subject to the terms and rights of its original provider.
