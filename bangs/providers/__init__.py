"""Replaceable provider contracts for BANGS external observations."""

from .base import (
    AccommodationProvider, EquipmentProvider, FuelPriceProvider, MaterialProvider,
    ProviderQueryContext, ProviderResult, ProviderStatus, RouteProvider,
    SupplierProvider, TollProvider, safe_provider_query,
)
from .manual import ManualObservationProvider

__all__ = [
    "AccommodationProvider", "EquipmentProvider", "FuelPriceProvider",
    "ManualObservationProvider", "MaterialProvider", "ProviderQueryContext",
    "ProviderResult", "ProviderStatus", "RouteProvider", "SupplierProvider",
    "TollProvider", "safe_provider_query",
]
