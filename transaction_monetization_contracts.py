"""Neutral transaction-domain contracts for future ObraSignal monetization.

Architecture only. This module does not bill, refer, book, lend, insure, rank or
recommend. It preserves future transaction/partner revenue options while keeping
commercial remuneration outside recommendation ranking.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Optional


class RegulatoryState(str, Enum):
    UNKNOWN = "UNKNOWN"
    NOT_REQUIRED = "NOT_REQUIRED"
    AUTHORIZED_PARTNER = "AUTHORIZED_PARTNER"
    CLEARED = "CLEARED"
    BLOCKED = "BLOCKED"


class MonetizationState(str, Enum):
    NOT_EVALUATED = "NOT_EVALUATED"
    ELIGIBLE = "ELIGIBLE"
    BLOCKED = "BLOCKED"
    DISABLED = "DISABLED"


@dataclass(frozen=True)
class Supplier:
    supplier_id: str
    name: str
    jurisdiction: str = ""
    compliance_status: str = "unknown"


@dataclass(frozen=True)
class Quote:
    quote_id: str
    supplier_id: str
    currency: str
    amount: Optional[Decimal] = None
    lead_time_days: Optional[int] = None
    payment_terms: str = ""
    compliance_status: str = "unknown"


@dataclass(frozen=True)
class Partner:
    partner_id: str
    name: str
    partner_type: str
    jurisdiction: str = ""
    regulatory_state: RegulatoryState = RegulatoryState.UNKNOWN
    disclosure_required: bool = False


@dataclass(frozen=True)
class Transaction:
    transaction_id: str
    transaction_type: str
    contractor_id: str
    supplier_id: str = ""
    quote_id: str = ""
    currency: str = ""
    gross_value: Optional[Decimal] = None
    status: str = "proposed"


@dataclass(frozen=True)
class Referral:
    referral_id: str
    transaction_id: str
    partner_id: str
    referral_type: str
    disclosed: bool = False


@dataclass(frozen=True)
class Commission:
    commission_id: str
    transaction_id: str
    partner_id: str
    currency: str
    amount: Optional[Decimal] = None
    rate: Optional[Decimal] = None
    status: str = "pending"


@dataclass(frozen=True)
class FinancingRoute:
    route_id: str
    transaction_id: str
    partner_id: str
    jurisdiction: str
    regulatory_state: RegulatoryState = RegulatoryState.UNKNOWN
    term_days: Optional[int] = None
    status: str = "proposed"

    @property
    def partner_route_eligible(self) -> bool:
        return self.regulatory_state in {
            RegulatoryState.AUTHORIZED_PARTNER,
            RegulatoryState.CLEARED,
        }


@dataclass(frozen=True)
class InsuranceRoute:
    route_id: str
    transaction_id: str
    partner_id: str
    jurisdiction: str
    regulatory_state: RegulatoryState = RegulatoryState.UNKNOWN
    coverage_type: str = ""
    status: str = "proposed"

    @property
    def partner_route_eligible(self) -> bool:
        return self.regulatory_state in {
            RegulatoryState.AUTHORIZED_PARTNER,
            RegulatoryState.CLEARED,
        }


@dataclass(frozen=True)
class Booking:
    booking_id: str
    transaction_id: str
    partner_id: str
    booking_type: str
    status: str = "proposed"
    external_reference: str = ""


@dataclass(frozen=True)
class Conversion:
    conversion_id: str
    origin_type: str
    origin_id: str
    transaction_id: str
    occurred_at: str
    value_created: Optional[Decimal] = None
    value_created_currency: str = ""


@dataclass(frozen=True)
class MonetizationAssessment:
    customer_experience_preserved: bool
    reduces_cost_or_friction: bool
    conflict_controlled: bool
    regulatory_clearance: bool
    trust_preserved: bool
    margin_justifies_complexity: bool
    measurable_and_auditable: bool

    @property
    def state(self) -> MonetizationState:
        return (
            MonetizationState.ELIGIBLE
            if all(
                (
                    self.customer_experience_preserved,
                    self.reduces_cost_or_friction,
                    self.conflict_controlled,
                    self.regulatory_clearance,
                    self.trust_preserved,
                    self.margin_justifies_complexity,
                    self.measurable_and_auditable,
                )
            )
            else MonetizationState.BLOCKED
        )

    @property
    def failed_checks(self) -> tuple[str, ...]:
        checks = {
            "customer_experience_preserved": self.customer_experience_preserved,
            "reduces_cost_or_friction": self.reduces_cost_or_friction,
            "conflict_controlled": self.conflict_controlled,
            "regulatory_clearance": self.regulatory_clearance,
            "trust_preserved": self.trust_preserved,
            "margin_justifies_complexity": self.margin_justifies_complexity,
            "measurable_and_auditable": self.measurable_and_auditable,
        }
        return tuple(name for name, passed in checks.items() if not passed)


def evaluate_monetization_gate(**checks) -> MonetizationAssessment:
    """Fail closed unless all seven explicit monetization gates are supplied/pass."""
    required = {
        "customer_experience_preserved",
        "reduces_cost_or_friction",
        "conflict_controlled",
        "regulatory_clearance",
        "trust_preserved",
        "margin_justifies_complexity",
        "measurable_and_auditable",
    }
    unknown = set(checks) - required
    missing = required - set(checks)
    if unknown:
        raise TypeError(f"unknown monetization gate checks: {sorted(unknown)}")
    if missing:
        raise ValueError(f"missing monetization gate checks: {sorted(missing)}")
    return MonetizationAssessment(**{name: bool(checks[name]) for name in required})


# Deliberately remuneration-free. A future recommendation engine may consume
# these economics, but Commission/Referral/Partner payment data is not accepted.
@dataclass(frozen=True)
class SupplierEconomicFit:
    supplier_id: str
    landed_cost: Optional[Decimal]
    quality_score: Optional[Decimal]
    compliance_passed: bool
    lead_time_days: Optional[int]
    reliability_score: Optional[Decimal]
    payment_terms_score: Optional[Decimal]
    risk_score: Optional[Decimal]
    contractor_economic_fit: Optional[Decimal]
