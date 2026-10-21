from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256
from datetime import datetime
from typing import Iterable

from .evidence import Availability, EvidenceBasis, RequirementBasis, SourceEvidence, TaxBasis, Visibility, validate_evidence_url
from .money import Money, as_decimal
from .units import convert_quantity, normalize_unit

@dataclass(frozen=True, slots=True)
class MaterialRequirement:
    material_id: str
    name: str
    quantity: Decimal | None
    unit: str | None
    basis: RequirementBasis
    category: str | None = None
    specification: str | None = None
    required_grade: str | None = None
    standard: str | None = None
    equivalent_allowed: bool | None = None
    location: str | None = None
    notes: str | None = None

    def __post_init__(self) -> None:
        mid = str(self.material_id or "").strip()
        name = str(self.name or "").strip()
        if not mid or len(mid) > 128 or not name or len(name) > 300:
            raise ValueError("material_id and name are required")
        for field_name, value, limit in (
            ("category", self.category, 200), ("specification", self.specification, 4000),
            ("required_grade", self.required_grade, 500), ("standard", self.standard, 500),
            ("location", self.location, 1000), ("notes", self.notes, 4000),
        ):
            if value is not None and len(str(value)) > limit:
                raise ValueError(f"{field_name} too long")
        object.__setattr__(self, "material_id", mid)
        object.__setattr__(self, "name", name)
        if self.quantity is None:
            if self.unit is not None:
                normalize_unit(self.unit)
            return
        q = as_decimal(self.quantity)
        if q < 0:
            raise ValueError("material quantity must be non-negative")
        if self.unit is None:
            raise ValueError("known material quantity requires a unit")
        object.__setattr__(self, "quantity", q)
        object.__setattr__(self, "unit", normalize_unit(self.unit))

@dataclass(frozen=True, slots=True)
class SupplierCandidate:
    supplier_id: str
    name: str
    country: str | None = None
    location: str | None = None
    website: str | None = None
    material_categories: tuple[str, ...] = ()
    delivery_available: bool | None = None
    distance_to_project_km: Decimal | None = None
    source_basis: EvidenceBasis = EvidenceBasis.UNKNOWN

    def __post_init__(self) -> None:
        sid = str(self.supplier_id or "").strip()
        name = str(self.name or "").strip()
        if not sid or len(sid) > 180 or not name or len(name) > 300:
            raise ValueError("supplier_id and name are required")
        if self.location is not None and len(str(self.location)) > 1000:
            raise ValueError("supplier location too long")
        if len(self.material_categories) > 100 or any(len(str(item)) > 200 for item in self.material_categories):
            raise ValueError("supplier material categories too large")
        object.__setattr__(self, "supplier_id", sid)
        object.__setattr__(self, "name", name)
        if self.website is not None:
            object.__setattr__(self, "website", validate_evidence_url(self.website))
        if self.distance_to_project_km is not None:
            distance = as_decimal(self.distance_to_project_km)
            if distance < 0:
                raise ValueError("supplier distance cannot be negative")
            object.__setattr__(self, "distance_to_project_km", distance)

@dataclass(frozen=True, slots=True)
class MaterialPriceObservation:
    observation_id: str
    material_id: str
    supplier_id: str | None
    unit: str
    unit_price: Money
    tax_basis: TaxBasis
    evidence: SourceEvidence
    visibility: Visibility
    tenant_id: str | None = None
    minimum_quantity: Decimal | None = None
    availability: Availability = Availability.UNKNOWN
    delivery_available: bool | None = None
    location: str | None = None
    confidence: Decimal | None = None
    flags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        oid = str(self.observation_id or "").strip()
        mid = str(self.material_id or "").strip()
        if not oid or len(oid) > 180 or not mid or len(mid) > 128:
            raise ValueError("observation_id and material_id are required")
        if self.supplier_id is not None and len(str(self.supplier_id)) > 180:
            raise ValueError("supplier_id too long")
        if self.location is not None and len(str(self.location)) > 1000:
            raise ValueError("observation location too long")
        if len(self.flags) > 50 or any(len(str(flag)) > 120 for flag in self.flags):
            raise ValueError("observation flags too large")
        object.__setattr__(self, "observation_id", oid)
        object.__setattr__(self, "material_id", mid)
        object.__setattr__(self, "unit", normalize_unit(self.unit))
        if self.minimum_quantity is not None:
            minimum = as_decimal(self.minimum_quantity)
            if minimum < 0:
                raise ValueError("minimum quantity cannot be negative")
            object.__setattr__(self, "minimum_quantity", minimum)
        if self.confidence is not None:
            confidence = as_decimal(self.confidence)
            if confidence < 0 or confidence > 1:
                raise ValueError("confidence must be between 0 and 1")
            object.__setattr__(self, "confidence", confidence)
        if self.visibility is Visibility.TENANT_PRIVATE and not str(self.tenant_id or "").strip():
            raise ValueError("tenant-private observation requires tenant_id")
        if self.visibility is Visibility.PUBLIC and self.tenant_id is not None:
            raise ValueError("public observation must not carry tenant_id")

    def normalized_unit_price(self, target_unit: str) -> Money:
        # Price conversion is inverse to quantity conversion. A price of X/t becomes
        # X/1000 per kg. Ask the quantity converter how many source units equal one target unit.
        source_units_per_target = convert_quantity(Decimal("1"), target_unit, self.unit)
        return self.unit_price.times(source_units_per_target)


def observation_fingerprint(observation: MaterialPriceObservation) -> str:
    parts = (
        observation.material_id,
        observation.supplier_id or "",
        observation.unit,
        format(observation.unit_price.amount, "f"),
        observation.unit_price.currency,
        observation.tax_basis.value,
        observation.evidence.basis.value,
        observation.evidence.observed_at.isoformat(),
        observation.evidence.source_url or observation.evidence.source_ref or observation.evidence.source_name,
        observation.visibility.value,
        observation.tenant_id or "",
    )
    return sha256("\x1f".join(parts).encode("utf-8")).hexdigest()


def dedupe_observations(observations: Iterable[MaterialPriceObservation]) -> tuple[MaterialPriceObservation, ...]:
    seen: set[str] = set()
    result: list[MaterialPriceObservation] = []
    for item in observations:
        fp = observation_fingerprint(item)
        if fp not in seen:
            result.append(item)
            seen.add(fp)
    return tuple(result)

@dataclass(frozen=True, slots=True)
class PriceObservationReview:
    observation: MaterialPriceObservation
    state: str
    reason: str | None = None


def review_price_outliers(
    observations: Iterable[MaterialPriceObservation],
    *,
    ratio_threshold: Decimal | int | str | float = Decimal("3"),
) -> tuple[PriceObservationReview, ...]:
    """Mark extreme same-unit/same-currency prices; never discard them."""
    items = tuple(observations)
    threshold = as_decimal(ratio_threshold)
    if threshold <= 1:
        raise ValueError("ratio_threshold must be greater than 1")
    grouped: dict[tuple[str, str, str], list[MaterialPriceObservation]] = {}
    for item in items:
        grouped.setdefault((item.material_id, item.unit, item.unit_price.currency), []).append(item)
    reviews: list[PriceObservationReview] = []
    for item in items:
        group = grouped[(item.material_id, item.unit, item.unit_price.currency)]
        if len(group) < 3:
            reviews.append(PriceObservationReview(item, "NEEDS_VERIFICATION", "insufficient_peer_observations"))
            continue
        ordered = sorted(x.unit_price.amount for x in group)
        mid = len(ordered) // 2
        median = ordered[mid] if len(ordered) % 2 else (ordered[mid - 1] + ordered[mid]) / Decimal("2")
        value = item.unit_price.amount
        is_outlier = (median > 0 and (value > median * threshold or value * threshold < median)) or (median == 0 and value > 0)
        reviews.append(PriceObservationReview(item, "OUTLIER" if is_outlier else "NORMAL", "extreme_peer_ratio" if is_outlier else None))
    return tuple(reviews)
