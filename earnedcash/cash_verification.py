from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum


ZERO = Decimal("0")


class CashEvidenceKind(str, Enum):
    BANK_RECEIPT = "BANK_RECEIPT"
    CREDIT_NOTE = "CREDIT_NOTE"


class CashVerificationState(str, Enum):
    VERIFIED = "VERIFIED"
    UNKNOWN = "UNKNOWN"
    MISMATCH = "MISMATCH"


@dataclass(frozen=True)
class CashEvidence:
    evidence_ref: str
    kind: CashEvidenceKind
    tenant_id: str
    project_id: str
    currency: str
    amount: Decimal
    independently_verified: bool


@dataclass(frozen=True)
class CashVerificationResult:
    state: CashVerificationState
    verified_amount: Decimal
    evidence_ref: str | None
    reason: str


def verify_cash_evidence(
    *,
    tenant_id: str,
    project_id: str,
    currency: str,
    claimed_amount: Decimal,
    evidence: CashEvidence,
) -> CashVerificationResult:
    if not claimed_amount.is_finite() or claimed_amount < ZERO:
        raise ValueError("invalid claimed amount")
    if not evidence.amount.is_finite() or evidence.amount < ZERO:
        return CashVerificationResult(
            CashVerificationState.UNKNOWN, ZERO, None, "INVALID_EVIDENCE_AMOUNT"
        )
    if evidence.kind != CashEvidenceKind.BANK_RECEIPT:
        return CashVerificationResult(
            CashVerificationState.MISMATCH,
            ZERO,
            evidence.evidence_ref or None,
            "NON_CASH_EVIDENCE_KIND",
        )
    if not evidence.independently_verified:
        return CashVerificationResult(
            CashVerificationState.UNKNOWN, ZERO, evidence.evidence_ref,
            "EVIDENCE_NOT_INDEPENDENTLY_VERIFIED",
        )
    expected = (
        tenant_id,
        project_id,
        currency.upper(),
        claimed_amount,
    )
    observed = (
        evidence.tenant_id,
        evidence.project_id,
        evidence.currency.upper(),
        evidence.amount,
    )
    if observed != expected:
        return CashVerificationResult(
            CashVerificationState.MISMATCH, ZERO, evidence.evidence_ref,
            "CASH_EVIDENCE_SCOPE_OR_AMOUNT_MISMATCH",
        )
    if not evidence.evidence_ref.strip():
        return CashVerificationResult(
            CashVerificationState.UNKNOWN, ZERO, None, "EVIDENCE_REFERENCE_MISSING"
        )
    return CashVerificationResult(
        CashVerificationState.VERIFIED,
        claimed_amount,
        evidence.evidence_ref,
        "EXACT_SCOPE_AMOUNT_MATCH",
    )
