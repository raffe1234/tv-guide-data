from __future__ import annotations

from importlib import import_module
from typing import Protocol

from ..config import SourceConfig
from ..models import Programme


class SourceAdapter(Protocol):
    def fetch_and_parse(self, config: SourceConfig) -> list[Programme]: ...


def load_adapter(name: str) -> SourceAdapter:
    module = import_module(f"tv_guide_data.sources.{name}")
    return module.Adapter()
