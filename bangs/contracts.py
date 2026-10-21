from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from .money import Money, as_decimal

@dataclass(frozen=True, slots=True)
class ProjectLocation:
    label: str
    country_code: str | None = None
    address: str | None = None
    latitude: Decimal | None = None
    longitude: Decimal | None = None

    def __post_init__(self) -> None:
        label = str(self.label or "").strip()
        if not label or len(label) > 300:
            raise ValueError("project location label is required and bounded")
        if self.address is not None and len(str(self.address)) > 1000:
            raise ValueError("project address too long")
        object.__setattr__(self, "label", label)
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be supplied together")
        if self.latitude is not None:
            lat, lon = as_decimal(self.latitude), as_decimal(self.longitude)
            if lat < -90 or lat > 90 or lon < -180 or lon > 180:
                raise ValueError("coordinates out of bounds")
            object.__setattr__(self, "latitude", lat)
            object.__setattr__(self, "longitude", lon)
        if self.country_code is not None:
            cc = str(self.country_code).strip().upper()
            if len(cc) != 2 or not cc.isalpha():
                raise ValueError("country_code must be ISO alpha-2-like")
            object.__setattr__(self, "country_code", cc)

@dataclass(frozen=True, slots=True)
class CompanyContext:
    """Optional BANGS inputs only; not a parallel Company State."""
    tenant_id: str
    base_location: ProjectLocation | None = None
    fuel_consumption_l_per_100km: Decimal | None = None
    per_diem_rate: Money | None = None
    room_occupancy_policy: int | None = None
    vehicle_cost_per_km: Money | None = None
    paid_travel_time_rate_per_hour: Money | None = None
    cash_limit: Money | None = None

    def __post_init__(self) -> None:
        tenant = str(self.tenant_id or "").strip()
        if not tenant or len(tenant) > 128:
            raise ValueError("tenant_id is required and bounded")
        object.__setattr__(self, "tenant_id", tenant)
        if self.fuel_consumption_l_per_100km is not None:
            value = as_decimal(self.fuel_consumption_l_per_100km)
            if value < 0 or value > 100:
                raise ValueError("fuel consumption out of bounds")
            object.__setattr__(self, "fuel_consumption_l_per_100km", value)
        if self.room_occupancy_policy is not None and self.room_occupancy_policy <= 0:
            raise ValueError("room occupancy policy must be positive")
