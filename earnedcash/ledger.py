from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum


ZERO = Decimal("0")


class LedgerKind(str, Enum):
    APPLICATION = "APPLICATION"
    CERTIFICATE = "CERTIFICATE"
    INVOICE = "INVOICE"
    PAYMENT = "PAYMENT"
    CREDIT = "CREDIT"
    DEDUCTION = "DEDUCTION"


class Severity(str, Enum):
    P0 = "P0"
    P1 = "P1"
    REVIEW = "REVIEW"


@dataclass(frozen=True)
class LedgerRecord:
    record_id: str
    tenant_id: str
    customer_id: str
    project_id: str
    currency: str
    kind: LedgerKind
    amount: Decimal
    relates_to: str | None = None
    verified: bool = False
    due: bool | None = None


@dataclass(frozen=True)
class LedgerAnomaly:
    code: str
    severity: Severity
    record_id: str
    related_record_id: str | None
    detail: str


@dataclass(frozen=True)
class InvoicePosition:
    invoice_id: str
    amount: Decimal
    verified_cash: Decimal
    open_balance: Decimal
    due_unpaid: Decimal
    not_yet_due: Decimal
    unknown: bool
    evidence_chain: tuple[str, ...]


@dataclass(frozen=True)
class LedgerResult:
    positions: tuple[InvoicePosition, ...]
    anomalies: tuple[LedgerAnomaly, ...]
    verified_cash: Decimal
    due_unpaid: Decimal
    not_yet_due: Decimal
    unknown_value: Decimal

    @property
    def p0_count(self) -> int:
        return sum(1 for a in self.anomalies if a.severity == Severity.P0)


_ALLOWED_PARENT = {
    LedgerKind.CERTIFICATE: LedgerKind.APPLICATION,
    LedgerKind.INVOICE: LedgerKind.CERTIFICATE,
    LedgerKind.PAYMENT: LedgerKind.INVOICE,
    LedgerKind.CREDIT: LedgerKind.INVOICE,
    LedgerKind.DEDUCTION: LedgerKind.INVOICE,
}


def _scope_tuple(record: LedgerRecord) -> tuple[str, str, str, str]:
    return (record.tenant_id, record.customer_id, record.project_id, record.currency)


def reconcile_ledger(records: tuple[LedgerRecord, ...]) -> LedgerResult:
    anomalies: list[LedgerAnomaly] = []
    by_id: dict[str, LedgerRecord] = {}
    invalid: set[str] = set()

    for record in records:
        if not record.record_id:
            raise ValueError("record_id is required")
        if not all((record.tenant_id, record.customer_id, record.project_id, record.currency)):
            raise ValueError(f"scope fields are required: {record.record_id}")
        if not record.amount.is_finite() or record.amount < ZERO:
            raise ValueError(f"invalid amount: {record.record_id}")
        if record.record_id in by_id:
            anomalies.append(
                LedgerAnomaly(
                    code="DUPLICATE_RECORD_ID",
                    severity=Severity.P1,
                    record_id=record.record_id,
                    related_record_id=record.record_id,
                    detail="record_id must be unique inside an import",
                )
            )
            invalid.add(record.record_id)
        else:
            by_id[record.record_id] = record

    for record in records:
        expected_parent_kind = _ALLOWED_PARENT.get(record.kind)
        if expected_parent_kind is None:
            continue
        if not record.relates_to:
            anomalies.append(
                LedgerAnomaly(
                    code="MISSING_PARENT_REFERENCE",
                    severity=Severity.REVIEW,
                    record_id=record.record_id,
                    related_record_id=None,
                    detail=f"{record.kind.value} requires explicit lineage",
                )
            )
            invalid.add(record.record_id)
            continue

        parent = by_id.get(record.relates_to)
        if parent is None:
            anomalies.append(
                LedgerAnomaly(
                    code="UNKNOWN_PARENT_REFERENCE",
                    severity=Severity.REVIEW,
                    record_id=record.record_id,
                    related_record_id=record.relates_to,
                    detail="referenced record was not supplied",
                )
            )
            invalid.add(record.record_id)
            continue

        if record.tenant_id != parent.tenant_id:
            anomalies.append(
                LedgerAnomaly(
                    code="CROSS_TENANT_REFERENCE",
                    severity=Severity.P0,
                    record_id=record.record_id,
                    related_record_id=parent.record_id,
                    detail="cross-tenant lineage is forbidden",
                )
            )
            invalid.update((record.record_id, parent.record_id))
            continue

        if _scope_tuple(record) != _scope_tuple(parent):
            anomalies.append(
                LedgerAnomaly(
                    code="CROSS_SCOPE_REFERENCE",
                    severity=Severity.P1,
                    record_id=record.record_id,
                    related_record_id=parent.record_id,
                    detail="customer/project/currency scope mismatch",
                )
            )
            invalid.update((record.record_id, parent.record_id))
            continue

        if parent.kind != expected_parent_kind:
            anomalies.append(
                LedgerAnomaly(
                    code="WRONG_PARENT_KIND",
                    severity=Severity.P1,
                    record_id=record.record_id,
                    related_record_id=parent.record_id,
                    detail=f"expected {expected_parent_kind.value}, got {parent.kind.value}",
                )
            )
            invalid.add(record.record_id)

    invoices = [r for r in records if r.kind == LedgerKind.INVOICE]

    # The result object is tenant-scoped. Independent records from more than one
    # tenant must never be aggregated into a shared commercial result.
    tenant_ids = {r.tenant_id for r in records}
    if len(tenant_ids) > 1 and not any(a.severity == Severity.P0 for a in anomalies):
        anomalies.append(
            LedgerAnomaly(
                code="MULTI_TENANT_DATASET",
                severity=Severity.P0,
                record_id="*",
                related_record_id=None,
                detail="one reconciliation result cannot aggregate multiple tenants",
            )
        )
        invalid.update(r.record_id for r in invoices)

    # Decimal totals across currencies are economically meaningless. Until an
    # explicit FX model exists, mixed-currency datasets fail closed.
    currencies = {r.currency for r in records}
    if len(currencies) > 1:
        anomalies.append(
            LedgerAnomaly(
                code="MULTI_CURRENCY_DATASET",
                severity=Severity.P1,
                record_id="*",
                related_record_id=None,
                detail="mixed currencies require separate reconciliation",
            )
        )
        invalid.update(r.record_id for r in invoices)

    positions: list[InvoicePosition] = []
    verified_cash_total = ZERO
    due_unpaid_total = ZERO
    not_yet_due_total = ZERO
    unknown_total = ZERO

    for invoice in invoices:
        if invoice.record_id in invalid:
            unknown_total += invoice.amount
            continue

        certificate = by_id.get(invoice.relates_to or "")
        if (
            certificate is None
            or certificate.record_id in invalid
            or certificate.kind != LedgerKind.CERTIFICATE
        ):
            unknown_total += invoice.amount
            continue

        application = by_id.get(certificate.relates_to or "")
        chain_verified = bool(
            invoice.verified
            and certificate.verified
            and application is not None
            and application.verified
            and application.record_id not in invalid
        )

        linked = [
            r
            for r in records
            if r.relates_to == invoice.record_id
            and r.kind in (LedgerKind.PAYMENT, LedgerKind.CREDIT, LedgerKind.DEDUCTION)
            and r.record_id not in invalid
        ]
        verified_payments = sum(
            (r.amount for r in linked if r.kind == LedgerKind.PAYMENT and r.verified),
            ZERO,
        )
        conservative_all_payments = sum(
            (r.amount for r in linked if r.kind == LedgerKind.PAYMENT), ZERO
        )
        credits = sum(
            (r.amount for r in linked if r.kind == LedgerKind.CREDIT and r.verified),
            ZERO,
        )
        deductions = sum(
            (r.amount for r in linked if r.kind == LedgerKind.DEDUCTION and r.verified),
            ZERO,
        )

        if conservative_all_payments + credits + deductions > invoice.amount:
            anomalies.append(
                LedgerAnomaly(
                    code="OVERMATCHED_INVOICE",
                    severity=Severity.P1,
                    record_id=invoice.record_id,
                    related_record_id=None,
                    detail="payments/credits/deductions exceed invoice amount",
                )
            )
            unknown_total += invoice.amount
            continue

        # All observed payments reduce open balance conservatively so we never
        # overclaim recovery; only verified payments may become VERIFIED_CASH.
        open_balance = max(
            ZERO, invoice.amount - conservative_all_payments - credits - deductions
        )
        verified_cash = min(invoice.amount, verified_payments)
        verified_cash_total += verified_cash

        due_unpaid = ZERO
        not_yet_due = ZERO
        unknown = False
        if open_balance > ZERO:
            if not chain_verified:
                unknown = True
                unknown_total += open_balance
            elif invoice.due is True:
                due_unpaid = open_balance
                due_unpaid_total += open_balance
            elif invoice.due is False:
                not_yet_due = open_balance
                not_yet_due_total += open_balance
            else:
                unknown = True
                unknown_total += open_balance

        evidence_chain = tuple(
            rid
            for rid in (
                application.record_id if application else None,
                certificate.record_id,
                invoice.record_id,
            )
            if rid
        )
        positions.append(
            InvoicePosition(
                invoice_id=invoice.record_id,
                amount=invoice.amount,
                verified_cash=verified_cash,
                open_balance=open_balance,
                due_unpaid=due_unpaid,
                not_yet_due=not_yet_due,
                unknown=unknown,
                evidence_chain=evidence_chain,
            )
        )

    return LedgerResult(
        positions=tuple(positions),
        anomalies=tuple(anomalies),
        verified_cash=verified_cash_total,
        due_unpaid=due_unpaid_total,
        not_yet_due=not_yet_due_total,
        unknown_value=unknown_total,
    )
