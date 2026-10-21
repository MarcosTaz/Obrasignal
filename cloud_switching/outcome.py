from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Optional


class EvidenceStrength(str, Enum):
    MACHINE = "machine_verified"
    INVOICE = "invoice_verified"
    DOCUMENT = "document_verified"
    CUSTOMER = "customer_attested"
    PARTNER = "partner_attested"
    PUBLIC = "public_claim"
    UNVERIFIED = "unverified"


@dataclass(frozen=True)
class Evidence:
    source_id: str
    strength: EvidenceStrength
    independent: bool
    methodology_version: str


@dataclass(frozen=True)
class ForecastActual:
    forecast: Decimal
    actual: Optional[Decimal]
    evidence: Evidence

    @property
    def variance(self) -> Optional[Decimal]:
        return None if self.actual is None else self.actual - self.forecast

    @property
    def variance_pct(self) -> Optional[Decimal]:
        if self.actual is None or self.forecast == 0:
            return None
        return ((self.actual - self.forecast) / self.forecast * Decimal("100")).quantize(Decimal("0.01"))


@dataclass(frozen=True)
class MigrationOutcomeRecord:
    case_id: str
    source_platform: str
    destination_platform: str
    workload_class: str
    migration_strategy: str
    migration_cost: ForecastActual
    duration_days: ForecastActual
    annual_run_cost: ForecastActual
    downtime_minutes: ForecastActual
    provider_incentive: ForecastActual

    def verified_for_benchmark(self) -> bool:
        fields = (
            self.migration_cost,
            self.duration_days,
            self.annual_run_cost,
            self.downtime_minutes,
            self.provider_incentive,
        )
        disallowed = {EvidenceStrength.PARTNER, EvidenceStrength.PUBLIC, EvidenceStrength.UNVERIFIED}
        return all(
            field.actual is not None
            and field.evidence.independent
            and field.evidence.strength not in disallowed
            for field in fields
        )
