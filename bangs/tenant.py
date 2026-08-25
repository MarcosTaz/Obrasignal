from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

from .evidence import Visibility

T = TypeVar("T")

@dataclass(frozen=True, slots=True)
class ScopedObservation(Generic[T]):
    observation_id: str
    value: T
    visibility: Visibility
    tenant_id: str | None

    def __post_init__(self) -> None:
        if self.visibility is Visibility.TENANT_PRIVATE and not str(self.tenant_id or "").strip():
            raise ValueError("private observation requires tenant_id")
        if self.visibility is Visibility.PUBLIC and self.tenant_id is not None:
            raise ValueError("public observation cannot carry tenant_id")

class TenantObservationStore(Generic[T]):
    """Owned-module memory boundary; production persistence can implement the same semantics."""
    def __init__(self) -> None:
        self._items: dict[str, ScopedObservation[T]] = {}

    def put(self, observation: ScopedObservation[T]) -> None:
        existing = self._items.get(observation.observation_id)
        if existing == observation:
            return
        if existing is not None and existing != observation:
            raise ValueError("observation_id collision")
        self._items[observation.observation_id] = observation

    def get(self, observation_id: str, *, tenant_id: str) -> T | None:
        item = self._items.get(observation_id)
        if item is None:
            return None
        if item.visibility is Visibility.PUBLIC or item.tenant_id == tenant_id:
            return item.value
        return None

    def list_visible(self, *, tenant_id: str) -> tuple[T, ...]:
        return tuple(
            item.value for item in self._items.values()
            if item.visibility is Visibility.PUBLIC or item.tenant_id == tenant_id
        )
