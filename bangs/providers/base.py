from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Generic, Protocol, TypeVar

T = TypeVar("T")
Q = TypeVar("Q")

class ProviderStatus(str, Enum):
    OK = "OK"
    UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    TIMEOUT = "PROVIDER_TIMEOUT"
    RATE_LIMITED = "PROVIDER_RATE_LIMITED"
    INVALID_RESPONSE = "PROVIDER_INVALID_RESPONSE"

@dataclass(frozen=True, slots=True)
class ProviderQueryContext:
    timeout_seconds: float = 10.0
    max_results: int = 20

    def __post_init__(self) -> None:
        if not (0.1 <= float(self.timeout_seconds) <= 60.0):
            raise ValueError("provider timeout must be bounded to 0.1..60 seconds")
        if not (1 <= int(self.max_results) <= 100):
            raise ValueError("provider results must be bounded to 1..100")

@dataclass(frozen=True, slots=True)
class ProviderResult(Generic[T]):
    status: ProviderStatus
    items: tuple[T, ...] = ()
    error_code: str | None = None

    @property
    def available(self) -> bool:
        return self.status is ProviderStatus.OK

class Provider(Protocol[Q, T]):
    provider_name: str
    def query(self, query: Q, context: ProviderQueryContext) -> ProviderResult[T]: ...

class MaterialProvider(Provider[object, object], Protocol): ...
class SupplierProvider(Provider[object, object], Protocol): ...
class EquipmentProvider(Provider[object, object], Protocol): ...
class RouteProvider(Provider[object, object], Protocol): ...
class FuelPriceProvider(Provider[object, object], Protocol): ...
class TollProvider(Provider[object, object], Protocol): ...
class AccommodationProvider(Provider[object, object], Protocol): ...


def safe_provider_query(provider: Provider[Q, T], query: Q, context: ProviderQueryContext) -> ProviderResult[T]:
    """Bound provider results and fail closed without translating failure into zero cost."""
    try:
        result = provider.query(query, context)
    except TimeoutError:
        return ProviderResult(status=ProviderStatus.TIMEOUT, error_code="timeout")
    except Exception:
        return ProviderResult(status=ProviderStatus.UNAVAILABLE, error_code="provider_exception")
    if not isinstance(result, ProviderResult):
        return ProviderResult(status=ProviderStatus.INVALID_RESPONSE, error_code="invalid_result_type")
    if len(result.items) > context.max_results:
        return ProviderResult(status=result.status, items=result.items[: context.max_results], error_code=result.error_code)
    return result
