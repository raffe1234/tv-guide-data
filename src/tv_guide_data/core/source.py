from __future__ import annotations

from abc import ABC, abstractmethod
from importlib import import_module

from .models import GuideConfig, Programme, ProviderConfig


class SourceProvider(ABC):
    @abstractmethod
    def fetch(self, guide: GuideConfig, provider: ProviderConfig) -> list[Programme]:
        """Fetch and parse programmes for one provider."""


def load_provider(path: str) -> SourceProvider:
    module_name, separator, class_name = path.partition(":")
    if not separator:
        raise ValueError(f"Adapter must use module:Class syntax: {path}")
    module = import_module(module_name)
    provider_class = getattr(module, class_name)
    instance = provider_class()
    if not isinstance(instance, SourceProvider):
        raise TypeError(f"{path} is not a SourceProvider")
    return instance
