from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation


class LeakageReconciliationError(ValueError):
    """Raised when recovery-ledger inputs violate a fail-closed accounting invariant."""


def _amount(value: object, *, label: str) -> Decimal:
    try:
        amount = Decimal(str(value).strip())
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise LeakageReconciliationError(f"{label} must be a decimal") from exc
    if not amount.is_finite() or amount < 0:
        raise LeakageReconciliationError(f"{label} must be a non-negative finite decimal")
    return amount


def _currency(value: object) -> str:
    code = str(value or "").strip().upper()
    if len(code) != 3 or not code.isascii() or not code.isalpha():
        raise LeakageReconciliationError("currency must be a three-letter ASCII code")
    return code


@dataclass(frozen=True)
class RecoveryLedgerSnapshot:
    documented_cost: Decimal
    mitigation: Decimal
    net_documented_exposure: Decimal
    evidence_supported: Decimal
    claimed: Decimal
    approved: Decimal
    settled: Decimal
    unsupported_exposure: Decimal
    supported_unclaimed: Decimal
    claimed_unapproved: Decimal
    approved_unsettled: Decimal
    supported_unsettled: Decimal
    currency: str
    signals: tuple[str, ...]
    reconciliation_hash: str

    def as_dict(self) -> dict[str, object]:
        return {
            "documented_cost": str(self.documented_cost),
            "mitigation": str(self.mitigation),
            "net_documented_exposure": str(self.net_documented_exposure),
            "evidence_supported": str(self.evidence_supported),
            "claimed": str(self.claimed),
            "approved": str(self.approved),
            "settled": str(self.settled),
            "unsupported_exposure": str(self.unsupported_exposure),
            "supported_unclaimed": str(self.supported_unclaimed),
            "claimed_unapproved": str(self.claimed_unapproved),
            "approved_unsettled": str(self.approved_unsettled),
            "supported_unsettled": str(self.supported_unsettled),
            "currency": self.currency,
            "signals": list(self.signals),
            "reconciliation_hash": self.reconciliation_hash,
        }


def reconcile_recovery_ledger(
    *,
    documented_cost: object,
    mitigation: object = "0",
    evidence_supported: object = "0",
    claimed: object = "0",
    approved: object = "0",
    settled: object = "0",
    currency: object,
) -> RecoveryLedgerSnapshot:
    """Reconcile one supplier-side recovery ledger without inventing entitlement.

    `evidence_supported` is an externally/human-established commercial amount. This
    function never promotes unsupported cost into claimable value. The required
    monotonic chain is:

        net documented exposure >= evidence supported >= claimed >= approved >= settled

    A failed invariant is an accounting/data-quality exception, not a reason to
    silently reshape the numbers.
    """

    documented = _amount(documented_cost, label="documented_cost")
    mitigation_amount = _amount(mitigation, label="mitigation")
    supported = _amount(evidence_supported, label="evidence_supported")
    claimed_amount = _amount(claimed, label="claimed")
    approved_amount = _amount(approved, label="approved")
    settled_amount = _amount(settled, label="settled")
    code = _currency(currency)

    if mitigation_amount > documented:
        raise LeakageReconciliationError("mitigation cannot exceed documented cost")
    net = documented - mitigation_amount
    if supported > net:
        raise LeakageReconciliationError("evidence-supported amount cannot exceed net documented exposure")
    if claimed_amount > supported:
        raise LeakageReconciliationError("claimed amount cannot exceed evidence-supported amount")
    if approved_amount > claimed_amount:
        raise LeakageReconciliationError("approved amount cannot exceed claimed amount")
    if settled_amount > approved_amount:
        raise LeakageReconciliationError("settled amount cannot exceed approved amount")

    unsupported = net - supported
    supported_unclaimed = supported - claimed_amount
    claimed_unapproved = claimed_amount - approved_amount
    approved_unsettled = approved_amount - settled_amount
    supported_unsettled = supported - settled_amount

    signals: list[str] = []
    if unsupported > 0:
        signals.append("EVIDENCE_GAP")
    if supported_unclaimed > 0:
        signals.append("SUPPORTED_UNCLAIMED")
    if claimed_unapproved > 0:
        signals.append("CLAIM_DECISION_GAP")
    if approved_unsettled > 0:
        signals.append("APPROVED_UNSETTLED")
    if net == 0:
        signals.append("NO_NET_EXPOSURE")
    elif not signals:
        signals.append("FULLY_RECONCILED")

    canonical = {
        "documented_cost": str(documented),
        "mitigation": str(mitigation_amount),
        "net_documented_exposure": str(net),
        "evidence_supported": str(supported),
        "claimed": str(claimed_amount),
        "approved": str(approved_amount),
        "settled": str(settled_amount),
        "currency": code,
        "signals": signals,
    }
    reconciliation_hash = hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    return RecoveryLedgerSnapshot(
        documented_cost=documented,
        mitigation=mitigation_amount,
        net_documented_exposure=net,
        evidence_supported=supported,
        claimed=claimed_amount,
        approved=approved_amount,
        settled=settled_amount,
        unsupported_exposure=unsupported,
        supported_unclaimed=supported_unclaimed,
        claimed_unapproved=claimed_unapproved,
        approved_unsettled=approved_unsettled,
        supported_unsettled=supported_unsettled,
        currency=code,
        signals=tuple(signals),
        reconciliation_hash=reconciliation_hash,
    )
