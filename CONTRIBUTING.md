# Contributing

## Development setup

```bash
python -m pip install -e ".[dev]"
pre-commit install
pytest
```

## Add a source provider

1. Add a module below `src/tv_guide_data/sources/`.
2. Implement a class derived from `SourceProvider`.
3. Return `Programme` objects with timezone-aware start and stop values.
4. Add the provider path to a guide JSON file.
5. Add a local HTML fixture and parser tests.

A provider must use an official or otherwise legally reusable source. Do not
commit downloaded guide pages, tokens, cookies or subscriber-only data.

## Quality checks

```bash
ruff check .
ruff format --check .
mypy
pytest
```
