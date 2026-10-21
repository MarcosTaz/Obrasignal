"""Bounded research prototype for Construction Margin Intelligence.

No runtime/API wiring. This module deliberately separates observed economic facts
from inferred scope-change candidates and from contractual/legal entitlement.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

EvidenceStatus = Literal["UNPROVEN", "PARTIAL", "SUPPORTED"]
EntitlementStatus = Literal["UNKNOWN", "NEEDS_REVIEW", "SUPPORTED"]
ValuationStatus = Literal["UNKNOWN", "ESTIMATED", "SUPPORTED"]
RecoveryState = Literal[
    "DETECTED",
    "REVIEWED",
    "SUBMITTED",
    "APPROVED",
    "REJECTED",
    "PAID",
    "VOID",
]


@dataclass(frozen=True)
class MoneyRange:
    currency: str
    low: Decimal
    high: Decimal

    def __post_init__(self) -> None:
        currency = self.currency.strip().upper()
        if len(currency) != 3 or not currency.isalpha():
            raise ValueError("currency must be a three-letter code")
        if self.low < 0 or self.high < 0:
            raise ValueError("money range cannot be negative")
        if self.high < self.low:
            raise ValueError("high must be >= low")
        object.__setattr__(self, "currency", currency)


@dataclass(frozen=True)
class ChangeCandidate:
    account_id: str
    project_id: str
    candidate_id: str
    original_scope_ref: str
    changed_scope_ref: str
    evidence_refs: tuple[str, ...]
    evidence_status: EvidenceStatus = "UNPROVEN"
    entitlement_status: EntitlementStatus = "UNKNOWN"
    valuation_status: ValuationStatus = "UNKNOWN"
    estimated_cost_impact: MoneyRange | None = None
    proposed_recovery_value: MoneyRange | None = None
    submitted_value: Decimal | None = None
    approved_value: Decimal | None = None
    paid_value: Decimal | None = None
    recovery_state: RecoveryState = "DETECTED"

    def __post_init__(self) -> None:
        for field_name in ("account_id", "project_id", "candidate_id", "original_scope_ref", "changed_scope_ref"):
            if not getattr(self, field_name).strip():
                raise ValueError(f"{field_name} is required")
        if self.original_scope_ref == self.changed_scope_ref:
            raise ValueError("a change candidate requires distinct scope references")
        if any(not ref.strip() for ref in self.evidence_refs):
            raise ValueError("evidence refs must be non-empty")
        if self.evidence_status == "SUPPORTED" and not self.evidence_refs:
            raise ValueError("supported evidence requires at least one evidence reference")

        observed_values = (self.submitted_value, self.approved_value, self.paid_value)
        if any(value is not None and value < 0 for value in observed_values):
            raise ValueError("observed commercial values cannot be negative")

        if self.proposed_recovery_value is not None:
            if self.entitlement_status != "SUPPORTED" or self.valuation_status != "SUPPORTED":
                raise ValueError(
                    "proposed recovery value requires supported entitlement and supported valuation"
                )
            if self.estimated_cost_impact and self.proposed_recovery_value.currency != self.estimated_cost_impact.currency:
                raise ValueError("cost impact and proposed recovery currencies must match")

        state_requires = {
            "SUBMITTED": self.submitted_value is not None,
            "APPROVED": self.submitted_value is not None and self.approved_value is not None,
            "REJECTED": self.submitted_value is not None,
            "PAID": self.submitted_value is not None and self.approved_value is not None and self.paid_value is not None,
        }
        if self.recovery_state in state_requires and not state_requires[self.recovery_state]:
            raise ValueError(f"{self.recovery_state} requires observed lifecycle value evidence")

        if self.approved_value is not None and self.submitted_value is None:
            raise ValueError("approved value cannot exist without submitted value")
        if self.paid_value is not None and self.approved_value is None:
            raise ValueError("paid value cannot exist without approved value")

    @property
    def margin_at_risk(self) -> MoneyRange | None:
        """Economic exposure only; never a claim of recoverability or entitlement."""
        return self.estimated_cost_impact

    @property
    def realized_recovery(self) -> Decimal | None:
        """Observed paid value only. Never infer recovery from submission/approval."""
        return self.paid_value if self.recovery_state == "PAID" else None

    @property
    def can_assert_recoverable_value(self) -> bool:
        return (
            self.entitlement_status == "SUPPORTED"
            and self.valuation_status == "SUPPORTED"
            and self.proposed_recovery_value is not None
        )


def next_recovery_state(current: RecoveryState, requested: RecoveryState) -> RecoveryState:
    """Validate a bounded monotonic recovery lifecycle.

    REJECTED and VOID are terminal. PAID is terminal. APPROVED may progress only
    to PAID; SUBMITTED may progress to APPROVED or REJECTED.
    """

    allowed: dict[RecoveryState, tuple[RecoveryState, ...]] = {
        "DETECTED": ("REVIEWED", "VOID"),
        "REVIEWED": ("SUBMITTED", "VOID"),
        "SUBMITTED": ("APPROVED", "REJECTED", "VOID"),
        "APPROVED": ("PAID", "VOID"),
        "REJECTED": (),
        "PAID": (),
        "VOID": (),
    }
    if requested not in allowed[current]:
        raise ValueError(f"illegal recovery transition: {current} -> {requested}")
    return requested
