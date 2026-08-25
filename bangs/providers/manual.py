from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Iterable, TypeVar

from .base import ProviderQueryContext, ProviderResult, ProviderStatus

T = TypeVar("T")

@dataclass(slots=True)
class ManualObservationProvider(Generic[T]):
    """Provider boundary for already-supplied observations; performs no network IO."""
    items: Iterable[T]
    provider_name: str = "manual_observation"

    def query(self, _query: object, context: ProviderQueryContext) -> ProviderResult[T]:
        bounded = tuple(self.items)[: context.max_results]
        return ProviderResult(status=ProviderStatus.OK, items=bounded)
