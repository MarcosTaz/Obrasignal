from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from .costs import CostAssessment
from .money import Money

class FinancialExposureState(str, Enum):
    AVAILABLE = "AVAILABLE"
    PROVIDER_UNAVAILABLE = "ECONOMICS_PROVIDER_UNAVAILABLE"
    UNKNOWN = "UNKNOWN"

@dataclass(frozen=True, slots=True)
class FinancialExposure:
    state: FinancialExposureState
    working_capital: Money | None = None
    bond_exposure: Money | None = None
    retention: Money | None = None
    advance: Money | None = None
    payment_lag_days: int | None = None
    financial_cost: CostAssessment | None = None
    notes: tuple[str, ...] = ()

class FinancialExposureProvider(Protocol):
    provider_name: str
    def assess(self, opportunity_ref: str, tenant_id: str) -> FinancialExposure: ...


def assess_financial_exposure(opportunity_ref: str, tenant_id: str, provider: FinancialExposureProvider | None) -> FinancialExposure:
    if provider is None:
        return FinancialExposure(FinancialExposureState.PROVIDER_UNAVAILABLE)
    return provider.assess(opportunity_ref, tenant_id)
