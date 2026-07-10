# Contributing

Contributions are welcome: parser fixes, documentation, tests, new official sources, and stable channel mappings.

## Development setup

```bash
python -m venv .venv
python -m pip install -e ".[dev]"
pre-commit install
```

Before opening a pull request, run:

```bash
ruff check .
ruff format --check .
mypy
pytest
```

## Add a source

1. Create `config/sources/<source>.json`.
2. Add `src/tv_guide_data/sources/<source>.py` with an `Adapter` class exposing `fetch_and_parse(config)`.
3. Return `Programme` objects using the stable XMLTV IDs defined in the configuration.
4. Add an offline fixture and parser test under `tests/`.
5. Build only that source:

```bash
python scripts/build.py config/sources/<source>.json
```

## Reliability rules

- Prefer official or clearly permitted public schedule sources.
- Do not commit credentials, private URLs, or subscription data.
- Do not publish empty or obviously incomplete guides.
- Keep published XMLTV IDs stable.
- Do not reuse another channel's schedule as a fallback.
- Keep provider-specific parsing inside its adapter.
- Make parser tests independent of the internet.

## Pull requests

Keep pull requests focused. Explain the source, channel mapping, validation threshold, and any assumptions made about dates or time zones.
