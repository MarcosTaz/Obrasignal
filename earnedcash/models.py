from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Iterable


class TruthState(str, Enum):
    POTENTIAL_VALUE = "POTENTIAL_VALUE"
    CERTIFIED = "CERTIFIED"
    INVOICED = "INVOICED"
    DUE = "DUE"
    NOT_YET_DUE = "NOT_YET_DUE"
    RETENTION_HELD = "RETENTION_HELD"
    RETENTION_MATURED = "RETENTION_MATURED"
    FINAL_ACCOUNT_AGREED = "FINAL_ACCOUNT_AGREED"
    FINAL_ACCOUNT_PENDING = "FINAL_ACCOUNT_PENDING"
    DISPUTED = "DISPUTED"
    POTENTIALLY_RECOVERABLE = "POTENTIALLY_RECOVERABLE"
    EVIDENCE_SUPPORTED = "EVIDENCE_SUPPORTED"
    ACTION_REQUIRED = "ACTION_REQUIRED"
    PAID = "PAID"
    UNKNOWN = "UNKNOWN"


class BlockerType(str, Enum):
    NOT_DUE = "NOT_DUE"
    DEFECTS_PERIOD = "DEFECTS_PERIOD"
    VALID_DEFECT = "VALID_DEFECT"
    CLOSEOUT_DOCUMENT_MISSING = "CLOSEOUT_DOCUMENT_MISSING"
    CERTIFICATION_PENDING = "CERTIFICATION_PENDING"
    INVOICE_MISSING = "INVOICE_MISSING"
    PAYMENT_DELAY = "PAYMENT_DELAY"
    DISPUTE = "DISPUTE"
    DEDUCTION = "DEDUCTION"
    SET_OFF = "SET_OFF"
    LEGAL_REVIEW_NEEDED = "LEGAL_REVIEW_NEEDED"
    UNKNOWN = "UNKNOWN"


class EvidenceKind(str, Enum):
    CONTRACT = "CONTRACT"
    CERTIFICATE = "CERTIFICATE"
    INVOICE = "INVOICE"
    PAYMENT = "PAYMENT"
    RETENTION_RELEASE = "RETENTION_RELEASE"
    FINAL_ACCOUNT = "FINAL_ACCOUNT"
    DEDUCTION = "DEDUCTION"
    CLOSEOUT = "CLOSEOUT"


@dataclass(frozen=True)
class EvidenceItem:
    evidence_id: str
    kind: EvidenceKind
    amount: Decimal | None = None
    document_ref: str | None = None
    verified: bool = False


@dataclass(frozen=True)
class ProjectCashInput:
    tenant_id: str
    customer_id: str
    project_id: str
    currency: str
    certified_value: Decimal | None = None
    invoiced_value: Decimal | None = None
    paid_value: Decimal | None = None
    retention_held: Decimal | None = None
    retention_matured: bool | None = None
    final_account_agreed_value: Decimal | None = None
    payment_due: bool | None = None
    disputed_value: Decimal = Decimal("0")
    valid_deductions: Decimal = Decimal("0")
    evidence: tuple[EvidenceItem, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class RecoveryCase:
    tenant_id: str
    customer_id: str
    project_id: str
    currency: str
    category: str
    amount: Decimal
    state: TruthState
    blocker: BlockerType | None
    evidence_ids: tuple[str, ...]
    confidence: str
    action: str


@dataclass(frozen=True)
class ReconciliationResult:
    project_id: str
    currency: str
    cases: tuple[RecoveryCase, ...]
    verified_paid: Decimal
    potentially_recoverable: Decimal
    not_yet_due: Decimal
    disputed: Decimal
    unknown: bool

    @property
    def total_open_cases(self) -> int:
        return len(self.cases)


def verified_evidence(
    evidence: Iterable[EvidenceItem], kind: EvidenceKind
) -> tuple[EvidenceItem, ...]:
    return tuple(item for item in evidence if item.kind == kind and item.verified)
