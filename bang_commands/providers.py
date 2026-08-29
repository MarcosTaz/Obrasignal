from __future__ import annotations

from dataclasses import dataclass

from .contracts import BangProvider


@dataclass
class ProviderRegistry:
    _providers: dict[str, BangProvider]

    def __init__(self) -> None:
        self._providers = {}

    def register(self, capability: str, provider: BangProvider) -> None:
        key = capability.strip().upper()
        if not key:
            raise ValueError("capability is required")
        if key in self._providers:
            raise ValueError(f"provider already registered for {key}")
        self._providers[key] = provider

    def get(self, capability: str) -> BangProvider | None:
        return self._providers.get(capability.upper())

    def capabilities(self) -> tuple[str, ...]:
        return tuple(sorted(self._providers))
