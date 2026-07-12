# tv-guide-data

[![Test](https://github.com/raffe1234/tv-guide-data/actions/workflows/test.yml/badge.svg)](https://github.com/raffe1234/tv-guide-data/actions/workflows/test.yml)
[![Update TV guides](https://github.com/raffe1234/tv-guide-data/actions/workflows/update-guides.yml/badge.svg)](https://github.com/raffe1234/tv-guide-data/actions/workflows/update-guides.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

`tv-guide-data` builds and publishes a validated XMLTV guide for eight Spanish RTVE-related television channels.

Schedules are collected from independent public sources, normalized into a shared data model, validated, and rendered as both XML and gzip-compressed XMLTV files.

## Published guide

Use the compressed guide in Kodi, IPTV applications, or other XMLTV-compatible software:

```text
https://raw.githubusercontent.com/raffe1234/tv-guide-data/main/output/rtve.xml.gz
```

An uncompressed version is also published:

```text
https://raw.githubusercontent.com/raffe1234/tv-guide-data/main/output/rtve.xml
```

The XMLTV channel IDs must match the corresponding `tvg-id` values in the user's M3U playlist.

## Channels

| XMLTV ID | Channel | Schedule source |
| --- | --- | --- |
| `La.1.es` | La 1 | RTVE national schedule |
| `La.2.es` | La 2 | RTVE national schedule |
| `Canal.24.h.es` | Canal 24 Horas | RTVE national schedule |
| `Teledeporte.es` | Teledeporte | RTVE national schedule |
| `Clan.es` | Clan España | Dedicated RTVE Clan schedule |
| `TVE.Internacional.es` | TVE Internacional América | RTVE international schedule |
| `Star.es` | Star | RTVE international schedule |
| `Clan.Internacional.es` | Clan International | Movistar Argentina public content API |

Channel IDs are intentionally stable. Do not rename them without also updating every playlist that refers to them.

## How it works

The build process:

1. Loads the guide definition from `config/guides/rtve.json`.
2. Runs each configured source provider independently.
3. Maps source channels to exact XMLTV IDs.
4. Normalizes programmes into a shared internal model.
5. Deduplicates and validates the combined result.
6. Writes `output/rtve.xml`.
7. Writes `output/rtve.xml.gz`.

A failing required channel or structurally invalid guide stops the build before publication. Short future coverage and large schedule gaps are published with warnings instead of blocking the other channels.

## Provider architecture

Each external source is isolated in its own provider:

- `rtve.national` parses the complete national RTVE schedule.
- `rtve.clan` parses the dedicated schedule for Clan España.
- `rtve.international` parses TVE Internacional América and Star.
- `movistar.argentina` provides the current public schedule match for Clan International.

Providers return normalized programme objects and do not write XML directly. This keeps source-specific parsing separate from shared validation and XMLTV rendering.

Important project paths:

```text
config/guides/rtve.json

scripts/build.py

src/tv_guide_data/core/
src/tv_guide_data/sources/rtve/
src/tv_guide_data/sources/movistar/

tests/
tests/fixtures/

output/rtve.xml
output/rtve.xml.gz
```

## Requirements

- Python 3.12 or later
- Internet access to the configured public schedule sources

Install the project and development dependencies:

```bash
python3 -m pip install -e ".[dev]"
```

## Build locally

Build all configured guides:

```bash
python3 scripts/build.py
```

If the package has not been installed, run:

```bash
PYTHONPATH=src python3 scripts/build.py
```

The generated files are written to `output/`.

## Quality checks

Run the same checks used during development and continuous integration:

```bash
python3 -m ruff format .
python3 -m ruff check .
git diff --check
python3 -m mypy
python3 -m pytest
```

Validate the compressed output:

```bash
gzip -t output/rtve.xml.gz
```

Do not commit generated guide changes after a failed quality check.

## Validation

The project validates the combined guide before writing output. Checks include:

- every required channel has programme data;
- programme start and stop times are valid;
- stop times occur after start times;
- duplicate programmes are removed or rejected;
- overlapping programmes are detected;
- configured future-coverage and maximum-gap thresholds produce warnings;
- source channel mappings match the configured XMLTV IDs.

Validation thresholds are configured in `config/guides/rtve.json`. Coverage warnings do not block publication, but missing required channels and structurally invalid programmes still do.

Do not ignore repeated warnings. First determine whether the source is incomplete, the parser is broken, or the broadcaster has published a shorter schedule.

## Time zones

The guide uses `Europe/Madrid` as its configured time zone and writes XMLTV timestamps with numeric UTC offsets.

Unix timestamps returned by APIs are treated as absolute points in time before conversion to the guide time zone. Do not manually add or subtract a source country's UTC offset.

## GitHub Actions

The repository contains two main workflows:

- **Test** runs formatting, linting, type checking, and tests on pushes and pull requests.
- **Update TV guides** runs automatically at `02:17` and `14:17` UTC every day and can also be started manually.

After a successful scheduled build, changed XML and XML.GZ files are committed to `main` by `github-actions[bot]`.


### Coverage warning notifications

When a configured channel has too little future coverage, `Update TV guides` writes and publishes
the guide and then dispatches the separate
`All channels must have at least 24 hours of future coverage` workflow. A future schedule gap above
the configured threshold dispatches the separate
`No channel may have a future schedule gap longer than 6 hours` workflow.

The publication workflow stays successful, while the relevant warning workflow intentionally fails so
GitHub's normal failed-workflow notification has a warning-specific subject. Warning details and a
link to the successful publication run are included in the failed workflow summary.

The dispatch requests use the `WORKFLOW_DISPATCH_TOKEN` repository secret. Store a fine-grained
personal access token owned by the notification recipient in this secret. Restrict the token to this
repository and grant only `Actions: Read and write`. Using a user token makes GitHub attribute the
warning workflow run to that user, which allows that user's normal Actions failure notifications to
apply. The token is not used for guide publication or repository contents.

## Adding or changing a provider

When a schedule source or parser changes:

1. Keep the source in a dedicated provider.
2. Preserve the exact XMLTV channel IDs.
3. Add a small representative fixture.
4. Test channel mapping and timezone-aware timestamps.
5. Test invalid entries and deduplication.
6. Run the full quality-check suite.
7. Verify the published gzip file after the workflow completes.

Never copy one channel's schedule to another channel without direct evidence that both channels use the same feed.

See [CONTRIBUTING.md](CONTRIBUTING.md) for the general contribution workflow.

## Known limitations

### Clan España schedule horizon

The dedicated `Clan.es` source has historically published a shorter future schedule than the other channels. Its normal coverage should be understood before stricter coverage limits are added.

### Clan International source mapping

The Movistar Argentina `CLAN` schedule is the strongest currently available public match for `Clan.Internacional.es`. It has not been verified programme by programme against the authenticated RTVE Play+ stream and should therefore be monitored for regional differences.

Do not silently replace it with the regular `Clan.es` schedule. Public evidence has shown that Clan España and Clan International can carry different programmes at the same time.

### External source changes

RTVE's HTML and embedded application data, as well as the Movistar API, may change without notice. Fixtures, candidate counts, required-channel checks, and coverage validation are used to make such failures visible.

## Data policy

This project does not invent programme schedules. It only publishes data parsed from identified public schedule sources.

Broadcaster names and trademarks belong to their respective owners. This project is not affiliated with or endorsed by RTVE, Movistar, or Telefónica.

## License

The project code is licensed under the [MIT License](LICENSE).

The license applies to the software in this repository. Programme metadata and third-party trademarks may be subject to separate rights and terms from their original providers.
